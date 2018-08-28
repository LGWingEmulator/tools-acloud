#!/usr/bin/env python
#
# Copyright 2016 - The Android Open Source Project
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
"""This module holds constants used by the driver."""
BRANCH_PREFIX = "git_"
BUILD_TARGET_MAPPING = {
    # TODO: Add aosp goldfish targets and internal cf targets to vendor code
    # base.
    "aosp_phone": "aosp_cf_x86_phone-userdebug",
    "aosp_tablet": "aosp_cf_x86_tablet-userdebug",
}
SPEC_NAMES = {
    "nexus5", "nexus6", "nexus7_2012", "nexus7_2013", "nexus9", "nexus10"
}

DEFAULT_SERIAL_PORT = 1
LOGCAT_SERIAL_PORT = 2

# AVD types
TYPE_GCE = "gce"
TYPE_CF = "cuttlefish"
TYPE_GF = "goldfish"

# Image types
IMAGE_SRC_REMOTE = "remote_image"
IMAGE_SRC_LOCAL = "local_image"

# Instance types
INSTANCE_TYPE_REMOTE = "remote"
INSTANCE_TYPE_LOCAL = "local"

# Flavor types
FLAVOR_PHONE = "phone"
FLAVOR_AUTO = "auto"
FLAVOR_WEAR = "wear"
FLAVOR_TV = "tv"
FLAVOR_IOT = "iot"
FLAVOR_TABLET = "tablet"
FLAVOR_TABLET_3G = "tablet_3g"
ALL_FLAVORS = [
    FLAVOR_PHONE, FLAVOR_AUTO, FLAVOR_WEAR, FLAVOR_TV, FLAVOR_IOT,
    FLAVOR_TABLET, FLAVOR_TABLET_3G
]

USER_ANSWER_YES = {"y", "yes", "Y"}
