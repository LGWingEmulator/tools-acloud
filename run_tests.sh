#!/bin/bash

ACLOUD_DIR=`dirname $0`

if [ -z "$ANDROID_BUILD_TOP" ]; then
    echo "Missing ANDROID_BUILD_TOP env variable. Run 'lunch' first."
    exit 1
fi

# Runs all unit tests under tools/acloud.
for t in $(find $ACLOUD_DIR -type f -name "*_test.py");
do
    PYTHONPATH=$ANDROID_BUILD_TOP/tools python $t;
done
