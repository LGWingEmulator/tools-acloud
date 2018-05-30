#!/bin/bash

ACLOUD_DIR=$(dirname $(realpath $0))
TOOLS_DIR=$(dirname $ACLOUD_DIR)
THIRD_PARTY_DIR=$(dirname $TOOLS_DIR)/external/python

function get_python_path() {
    local python_path=$TOOLS_DIR
    local third_party_libs=(
        "dateutil"
    )
    for lib in $third_party_libs;
    do
        python_path=$THIRD_PARTY_DIR/$lib:$python_path
    done
    python_path=$python_path:$PYTHONPATH
    echo $python_path
}
