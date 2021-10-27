#!/bin/bash

set -euo pipefail

USER_PREFIX="jupyter_"

function eecho {
    echo -e "\e[1;31mERROR:" $@ "\e[0m" >/dev/stderr
}
