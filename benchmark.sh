#!/bin/bash

set -euo pipefail

SERVER=${1:-"htps://localhost:8000"}
COHORT_SIZE=${2:-10}
N_USERS_ACTIVE=${3:-${COHORT_SIZE}}

SCRIPTDIR=$(dirname $(readlink -f $0))

source ${SCRIPTDIR}/functions.sh

stat ${SCRIPTDIR}/password.txt > /dev/null
stat ${SCRIPTDIR}/users.txt > /dev/null

NUSERS=$(cat ${SCRIPTDIR}/users.txt | tr ' ' '\n' | wc -l)

if [[ $(( $(( NUSERS / COHORT_SIZE )) * COHORT_SIZE )) -ne ${NUSERS} ]]; then
    eecho "Cohort remainder is not 0"
    exit 1
fi

module load jupyter
export BM_USERPASS=$(cat ${SCRIPTDIR}/password.txt)
echo -n > ${SCRIPTDIR}/benchmark.log

for I in $(seq $(( NUSERS / COHORT_SIZE ))); do
    echo | tee -a ${SCRIPTDIR}/benchmark.log
    N_USERS_WORKING=$(( I * COHORT_SIZE ))
    echo "Testing ${N_USERS_WORKING} users" | tee -a ${SCRIPTDIR}/benchmark.log

    # login new cohort
    cat ${SCRIPTDIR}/users.txt \
        | tr ' ' '\n' \
        | head -${N_USERS_WORKING} \
        | tail -${COHORT_SIZE} \
        | tr ' \n' '\0' \
        | xargs -0 -P ${COHORT_SIZE} -I '{}' python ${SCRIPTDIR}/login.py '{}' ${SERVER} \
        > ${SCRIPTDIR}/benchmark-login.log 2>&1 \
        || true

    echo "    Initial login" | tee -a ${SCRIPTDIR}/benchmark.log

    python ${SCRIPTDIR}/analyse.py ${SCRIPTDIR}/benchmark-login.log \
        | tee -a ${SCRIPTDIR}/benchmark.log

    echo "    Login and work in existing session" | tee -a ${SCRIPTDIR}/benchmark.log

    # simulate working users
    time (
        cat ${SCRIPTDIR}/users.txt \
            | tr ' ' '\n' \
            | head -${N_USERS_WORKING} \
            | tr ' \n' '\0' \
            | xargs -0 -P ${N_USERS_ACTIVE} -I '{}' python ${SCRIPTDIR}/userwork.py '{}' ${SERVER} \
            || true
    ) > ${SCRIPTDIR}/benchmark-${I}.log 2>&1 || true

    python ${SCRIPTDIR}/analyse.py ${SCRIPTDIR}/benchmark-${I}.log \
        | tee -a ${SCRIPTDIR}/benchmark.log
done

# stop server for all users all users
cat ${SCRIPTDIR}/users.txt \
    | tr ' \n' '\0' \
    | xargs -0 -P ${COHORT_SIZE} -I '{}' python ${SCRIPTDIR}/stop-server.py '{}' ${SERVER} 2>&1 \
    > ${SCRIPTDIR}/benchmark-stop.log 2>&1 \
    || true

echo "Stopping servers" | tee -a ${SCRIPTDIR}/benchmark.log

python ${SCRIPTDIR}/analyse.py ${SCRIPTDIR}/benchmark-stop.log \
    | tee -a ${SCRIPTDIR}/benchmark.log
