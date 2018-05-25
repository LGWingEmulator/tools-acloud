#!/bin/bash

ACLOUD_DIR=`dirname $0`
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

if [ -z "$ANDROID_BUILD_TOP" ]; then
    echo "Missing ANDROID_BUILD_TOP env variable. Run 'lunch' first."
    exit 1
fi

function helper() {
    echo "usage: $0 [options]"
    echo "  options:"
    echo "    coverage, test all unit tests with coverage report"
}

function print_summary() {
    local test_results=$1
    local coverage_run=$2
    if [[ $coverage_run == "coverage" ]]; then
        PYTHONPATH=$ANDROID_BUILD_TOP/tools coverage report -m
        PYTHONPATH=$ANDROID_BUILD_TOP/tools coverage html
    fi
    if [[ $test_results -eq 0 ]]; then
        echo -e "${GREEN}All unittests pass${NC}!"
    else
        echo -e "${RED}There was a unittest failure${NC}"
    fi
}

function run_unittests() {
    local coverage_run=$1
    local run_cmd="python"
    local rc=0
    if [[ $coverage_run == "coverage" ]]; then
        # clear previously collected coverage data.
        PYTHONPATH=$ANDROID_BUILD_TOP/tools coverage erase
        run_cmd="coverage run --append"
    fi

    # Runs all unit tests under tools/acloud.
    for t in $(find $ACLOUD_DIR -type f -name "*_test.py");
    do
        if ! PYTHONPATH=$ANDROID_BUILD_TOP/tools $run_cmd $t; then
            rc=1
            echo -e "${RED}$t failed${NC}"
        fi
    done

    print_summary $rc $coverage_run
    exit $rc
}


case "$1" in
    'help')
        helper
        ;;
    'coverage')
        run_unittests "coverage"
        ;;
    *)
        run_unittests
        ;;
esac

