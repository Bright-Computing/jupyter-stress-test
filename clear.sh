#!/bin/bash

set -euo pipefail

HOST=${1:-localhost}
if [[ "${HOST}" = "-h" ]]; then
    echo "usage: clear {HOST}"
    exit 0
fi
SCRIPTDIR=$(dirname $(readlink -f $0))

source ${SCRIPTDIR}/functions.sh

echo "Get list of users"
USERS=$(cmsh -c 'user; list -f name' | egrep "^${USER_PREFIX}") || true

if [[ -z $(echo -n ${USERS} | sed -e 's/\n//') ]]; then
    exit 0
fi

echo "Stop all users' processes"
if [[ ${HOST} = "localhost" ]]; then
    echo ${USERS} \
        | tr ' \n' '\0' \
        | xargs -P $(nproc) -I '{}' -0 killall -9 -u '{}' 2>/dev/null \
        || true
else
    echo ${USERS} \
        | tr ' \n' '\0' \
        | ssh ${HOST} xargs -P $(nproc) -I '{}' -0 killall -9 -u '{}' 2>/dev/null \
        || true
fi

echo "Get homedirs"
HOMEDIRS=$(echo $USERS | tr ' \n' '\0' | xargs -P $(nproc) -I '{}' -0 getent passwd '{}' | cut -d: -f6)

echo "Remove users from cmsh"
CHUNK_SIZE=200
TEMPDIR=$(mktemp -d)
trap "rm -rf ${TEMPDIR}" EXIT
pushd ${TEMPDIR} > /dev/null
    echo ${USERS} | tr ' ' '\n' | split -l ${CHUNK_SIZE}
popd > /dev/null
for F in ${TEMPDIR}/*; do
    USER_CHUNK=$(cat ${F})
    echo "$(date --rfc-3339='seconds') Removing users $(head -1 ${F})..$(tail -1 ${F})"

    cmsh -c "user; foreach $(echo ${USER_CHUNK}) (remove); commit"
done

echo "Remove homedirs"
echo $HOMEDIRS | tr ' \n' '\0' | xargs -P $(nproc) -I '{}' -0 rm -rf '{}'
