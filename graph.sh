#!/bin/bash

set -euo pipefail

BENCHMARK_RES=${1:-benchmark.log}

if [[ "${BENCHMARK_RES}" = "-h" ]]; then
    echo "usage: benchmark LOGFILE"
    exit 0
fi


SCRIPTDIR=$(dirname $(readlink -f $0))

python3 -m venv ${SCRIPTDIR}/.venv
source ${SCRIPTDIR}/.venv/bin/activate
pip3 install matplotlib
python3 ${SCRIPTDIR}/graph.py ${BENCHMARK_RES}
