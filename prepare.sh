#!/bin/bash

set -euo pipefail

USERNUM=${1:-10}


SCRIPTDIR=$(dirname $(readlink -f $0))

source ${SCRIPTDIR}/functions.sh

echo "Generate list of users"
USERS=$(seq -w ${USERNUM} | awk -v P=${USER_PREFIX} '{print P$0}')

echo "Generate password"
PASSWORD=$(openssl rand 150 | tr -dc '0-Za-z' | head -c 16)
echo "USER PASSWORD: ${PASSWORD}"
touch ${SCRIPTDIR}/password.txt
chmod 600 ${SCRIPTDIR}/password.txt
echo ${PASSWORD} > ${SCRIPTDIR}/password.txt

echo "Create users"
USERS=$(seq -w ${USERNUM} | awk -v U=${USER_PREFIX} '{print U$0}')
echo ${USERS} | tr ' ' '\n' > ${SCRIPTDIR}/users.txt

CHUNK_SIZE=200
TEMPDIR=$(mktemp -d)
trap "rm -rf ${TEMPDIR}" EXIT

pushd ${TEMPDIR} > /dev/null
    split -l ${CHUNK_SIZE} ${SCRIPTDIR}/users.txt
popd > /dev/null
for F in ${TEMPDIR}/*; do
    USER_CHUNK=$(cat ${F})
    echo "$(date --rfc-3339='seconds') Adding users $(head -1 ${F})..$(tail -1 ${F})"
    (
        echo "user"
        for U in ${USER_CHUNK}; do
            echo "user add ${U}"
            echo "set password \"${PASSWORD}\""
            echo "commit"
        done
    ) | cmsh -f /dev/fd/0
done

exit 0

echo "Making sure users exist"

TRIES=30
while [[ ${TRIES} -gt 0 ]]; do
    sleep 1
    echo ${USERS} | tr ' \n' '\0' \
        | xargs -P $(nproc) -0 -I '{}' id -u '{}' >/dev/null \
        && break \
        || true
    TRIES=$(( ${TRIES} - 1 ))
done

if [[ ${TRIES} -eq 0 ]]; then
    eecho "Not all users were created"
    exit 1
fi

echo "Making sure homedirs created"
HOMEDIRS=$(echo $USERS | tr ' \n' '\0' | xargs -P $(nproc) -I '{}' -0 getent passwd '{}' | cut -d: -f6)
TRIES=30
while [[ ${TRIES} -gt 0 ]]; do
    sleep 1
    echo ${HOMEDIRS} | tr ' \n' '\0' \
        | xargs -P $(nproc) -0 -I '{}' stat '{}' >/dev/null \
        && break \
        || true
    TRIES=$(( ${TRIES} - 1 ))
done

if [[ ${TRIES} -eq 0 ]]; then
    eecho "Not all users were created"
    exit 1
fi

