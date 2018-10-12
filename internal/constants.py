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

# Remote image parameters
BUILD_TARGET = "build_target"
BUILD_BRANCH = "build_branch"
BUILD_ID = "build_id"

# AVD types
TYPE_GCE = "gce"
TYPE_CF = "cuttlefish"
TYPE_GF = "goldfish"

# Image types
IMAGE_SRC_REMOTE = "remote_image"
IMAGE_SRC_LOCAL = "local_image"

# AVD types in build target
AVD_TYPES_MAPPING = {
    TYPE_GCE: "gce",
    TYPE_CF: "cf",
    TYPE_GF: "sdk",
}

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

# HW Property
HW_ALIAS_CPUS = "cpu"
HW_ALIAS_RESOLUTION = "resolution"
HW_ALIAS_DPI = "dpi"
HW_ALIAS_MEMORY = "memory"
HW_ALIAS_DISK = "disk"
HW_PROPERTIES_CMD_EXAMPLE = (
    " %s:2,%s:1280x700,%s:160,%s:2g,%s:2g" %
    (HW_ALIAS_CPUS,
     HW_ALIAS_RESOLUTION,
     HW_ALIAS_DPI,
     HW_ALIAS_MEMORY,
     HW_ALIAS_DISK)
)
HW_PROPERTIES = [HW_ALIAS_CPUS, HW_ALIAS_RESOLUTION, HW_ALIAS_DPI,
                 HW_ALIAS_MEMORY, HW_ALIAS_DISK]
HW_X_RES = "x_res"
HW_Y_RES = "y_res"

USER_ANSWER_YES = {"y", "yes", "Y"}

# Cuttlefish groups
LIST_CF_USER_GROUPS = ["kvm", "libvirt", "cvdnetwork"]

DEFAULT_VNC_PORT = 6444
DEFAULT_ADB_PORT = 6520
VNC_PORT = "vnc_port"
ADB_PORT = "adb_port"

CMD_LAUNCH_CVD = "launch_cvd"
ENV_ANDROID_BUILD_TOP = "ANDROID_BUILD_TOP"

LOCALHOST_ADB_SERIAL = "127.0.0.1:%d"

SSH_BIN = "ssh"
ADB_BIN = "adb"
