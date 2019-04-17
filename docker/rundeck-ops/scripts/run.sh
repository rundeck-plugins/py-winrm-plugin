#!/usr/bin/env bash

run_helpers() {
  local -r helper=$1
  local -a scripts=( "${@:2}" )

  for script in "${scripts[@]}"
  do
      [[ ! -f "$script" ]] && {
          echo >&2 "WARN: $helper script not found. skipping: '$script'"
          continue
      }
      echo "### applying $helper script: $script"
      . "$script"
  done
}

wait_for_rundeck(){
  # Wait for server to start
  MAX_ATTEMPTS=200
  SLEEP=10

  echo "Waiting for rundeck to start. This will take about 2 minutes... "

  declare -i count=0
  while (( count <= MAX_ATTEMPTS ))
  do
      if ! rd system info >/dev/null 2>&1
      then  echo "Waiting. hang on..."; # output a progress character.
      else  break; # found successful startup message.
      fi
      (( count += 1 ))  ; # increment attempts counter.
      (( count == MAX_ATTEMPTS )) && {
          echo >&2 "FAIL: Reached max attempts to find success message in logfile. Exiting."
          exit 1
      }
      echo "."
      sleep $SLEEP; # wait before trying again.

  done
  echo "RUNDECK NODE $RUNDECK_NODE started successfully!!"

}

mkdir -p ~/.rd
cat > ~/.rd/rd.conf <<END

export RD_COLOR=0
export RD_OPTS="-Dfile.encoding=utf-8"
export RD_HTTP_TIMEOUT=500
export RD_URL=$RUNDECK_NODE_URL
export RD_BYPASS_URL=$RUNDECK_URL
export RD_USER=$RUNDECK_USER
export RD_PASSWORD=$RUNDECK_PASSWORD


END

wait_for_rundeck

### POST CONFIG
# RUN TEST POSTSTART SCRIPT
if [[ ! -z "$CONFIG_SCRIPT_POSTSTART" ]]
then
  IFS=','
  read -ra config_scripts <<< "$CONFIG_SCRIPT_POSTSTART"
  run_helpers "post-start" "${config_scripts[@]}"
else
  echo "### Post start config not set. skipping..."
fi

exit 0
