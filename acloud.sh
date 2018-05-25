#!/bin/bash
#!/usr/bin/env python
#
# Copyright 2018 - The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ACLOUD_DIR=$(dirname $(realpath $0))
TOOLS_DIR=$(dirname $ACLOUD_DIR)
# TODO: Add in path to 3rd party libs.
PYTHONPATH=${TOOLS_DIR}:$PYTHONPATH python ${ACLOUD_DIR}/public/acloud_main.py "$@"
