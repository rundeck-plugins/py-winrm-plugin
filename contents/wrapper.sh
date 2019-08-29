#!/bin/sh
PYTHON=${RD_CONFIG_INTERPRETER:-python}
cd `dirname $0`
${PYTHON} -u "$@"
