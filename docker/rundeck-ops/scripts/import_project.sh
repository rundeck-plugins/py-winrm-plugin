#!/bin/bash

#trap 'echo "rd fail" ; exit 0' EXIT
set -eu

echo "Sleeping 10s ..."
sleep 10

shopt -s nullglob
ARCHIVES=(/projects/*.{jar,zip,groovy})
shopt -u nullglob

echo "There are ${#ARCHIVES[*]} project archives to import"

for file in "${ARCHIVES[@]}"
do
	echo "Importing archive file $file ..."

    PROJECT_NAME=$(unzip -p "$file" META-INF/MANIFEST.MF|awk '/Rundeck-Archive-Project-Name:/ {print $2}' | tr -d '\r' )
    if ! rd projects info -p "$PROJECT_NAME" >/dev/null 2>&1
    then
	echo "Creating project: $PROJECT_NAME ..."
  if ! rd projects create -p "$PROJECT_NAME"
  then
    rc=$?
    echo >&2 "WARN: Failed to create project $PROJECT_NAME"
    exit $rc
  fi
	else
		echo >&2 "WARN: Project already exists: '$PROJECT_NAME' (skipping)"
	fi

 	rd projects archives import -f "$file" -p  "$PROJECT_NAME" --remove --noExecutions --include-config --include-acl

done

