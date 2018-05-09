#!/bin/bash

ACLOUD_DIR=`dirname $0`
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

if [ -z "$ANDROID_BUILD_TOP" ]; then
    echo "Missing ANDROID_BUILD_TOP env variable. Run 'lunch' first."
    exit 1
fi

rc=0
# Runs all unit tests under tools/acloud.
for t in $(find $ACLOUD_DIR -type f -name "*_test.py");
do
    if ! PYTHONPATH=$ANDROID_BUILD_TOP/tools python $t; then
      rc=1
      echo -e "${RED}$t failed${NC}"
    fi
done

if [[ $rc -eq 0 ]]; then
  echo -e "${GREEN}All unittests pass${NC}!"
else
  echo -e "${RED}There was a unittest failure${NC}"
fi
exit $rc
