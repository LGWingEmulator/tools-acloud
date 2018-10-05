#!/bin/bash

# Run any scripts in this dir and in any extra specified locations.
SCRIPT_LOCATIONS=(
  $(dirname $(realpath $0))
  "$ANDROID_BUILD_TOP/vendor/google/tools/acloud"
)

for script_dir in ${SCRIPT_LOCATIONS[*]};
do
  if [[ ! -d $script_dir ]]; then
    continue
  fi
  for script in $(ls ${script_dir}/*.sh);
  do
    if [[ $(basename $script) != $(basename $0) ]]; then
      $script
    fi
  done
done
