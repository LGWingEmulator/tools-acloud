#!/bin/bash

source $(dirname $(realpath $0))/utils.sh
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

function print_summary() {
    local test_results=$1
    local tmp_dir=$(mktemp -d)
    local rc_file=${ACLOUD_DIR}/.coveragerc
    PYTHONPATH=$(get_python_path) python -m coverage report -m
    PYTHONPATH=$(get_python_path) python -m coverage html -d $tmp_dir --rcfile=$rc_file
    echo "coverage report available at file://${tmp_dir}/index.html"

    if [[ $test_results -eq 0 ]]; then
        echo -e "${GREEN}All unittests pass${NC}!"
    else
        echo -e "${RED}There was a unittest failure${NC}"
    fi
}

function run_unittests() {
    local rc=0
    local run_cmd="python -m coverage run --append"

    # clear previously collected coverage data.
    PYTHONPATH=$(get_python_path) python -m coverage erase

    # Runs all unit tests under tools/acloud.
    for t in $(find $ACLOUD_DIR -type f -name "*_test.py");
    do
        if ! PYTHONPATH=$(get_python_path):$PYTHONPATH $run_cmd $t; then
            rc=1
            echo -e "${RED}$t failed${NC}"
        fi
    done

    print_summary $rc
    exit $rc
}

function check_env() {
    if [ -z "$ANDROID_BUILD_TOP" ]; then
        echo "Missing ANDROID_BUILD_TOP env variable. Run 'lunch' first."
        exit 1
    fi

    local missing_py_packages=false
    for py_lib in {absl-py,coverage,mock};
    do
        if ! pip list --format=legacy | grep $py_lib &> /dev/null; then
            echo "Missing required python package: $py_lib (pip install $py_lib)"
            missing_py_packages=true
        fi
    done
    if $missing_py_packages; then
        exit 1
    fi
}

check_env
run_unittests
