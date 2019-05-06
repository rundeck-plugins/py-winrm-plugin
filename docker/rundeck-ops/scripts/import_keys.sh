#!/bin/bash

#trap 'echo "rd fail" ; exit 0' EXIT
set -eu
shopt -s nullglob
ARCHIVES=(/storage/*.json)
shopt -u nullglob

echo "There are ${#ARCHIVES[*]} storage files"

for file in "${ARCHIVES[@]}"
do
    for row in $(cat "${file}" | jq -c .[]  | tr -d '^J'); do
        _jq() {
         echo ${row} | jq -r ${1}
        }
       echo "Creating key: $(_jq '.key')"

       tmpfile=$(mktemp /tmp/key.XXXXXX)
       echo $(_jq '.value') >  ${tmpfile}
       rd keys create -t password -p $(_jq '.key') -f ${tmpfile}
       rm ${tmpfile}
    done
done
