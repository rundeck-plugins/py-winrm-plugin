#!/usr/bin/env bash

set -eu

#compile
./gradlew clean build

cp build/libs/*.zip docker/rundeck/plugins
cd docker
make clean
make build
make start
