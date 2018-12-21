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
r"""Create args.

Defines the create arg parser that holds create specific args.
"""

import argparse
import os

from acloud import errors
from acloud.create import create_common
from acloud.internal import constants


CMD_CREATE = "create"


# TODO: Add this into main create args once create_cf/gf is deprecated.
def AddCommonCreateArgs(parser):
    """Adds arguments common to create parsers.

    Args:
        parser: ArgumentParser object, used to parse flags.
    """
    parser.add_argument(
        "--num",
        type=int,
        dest="num",
        required=False,
        default=1,
        help="Number of instances to create.")
    parser.add_argument(
        "--serial-log-file",
        type=str,
        dest="serial_log_file",
        required=False,
        help="Path to a *tar.gz file where serial logs will be saved "
             "when a device fails on boot.")
    parser.add_argument(
        "--logcat-file",
        type=str,
        dest="logcat_file",
        required=False,
        help="Path to a *tar.gz file where logcat logs will be saved "
             "when a device fails on boot.")
    parser.add_argument(
        "--autoconnect",
        action="store_true",
        dest="autoconnect",
        required=False,
        help="For each instance created, we will automatically creates both 2 "
             "ssh tunnels forwarding both adb & vnc. Then add the device to "
             "adb.")
    parser.add_argument(
        "--no-autoconnect",
        action="store_false",
        dest="autoconnect",
        required=False)
    parser.set_defaults(autoconnect=True)
    parser.add_argument(
        "--report-internal-ip",
        action="store_true",
        dest="report_internal_ip",
        required=False,
        help="Report internal ip of the created instance instead of external "
             "ip. Using the internal ip is used when connecting from another "
             "GCE instance.")
    parser.add_argument(
        "--network",
        type=str,
        dest="network",
        required=False,
        help="Set the network the GCE instance will utilize.")

    # TODO(b/118439885): Old arg formats to support transition, delete when
    # transistion is done.
    parser.add_argument(
        "--serial_log_file",
        type=str,
        dest="serial_log_file",
        required=False,
        help=argparse.SUPPRESS)
    parser.add_argument(
        "--logcat_file",
        type=str,
        dest="logcat_file",
        required=False,
        help=argparse.SUPPRESS)


def GetCreateArgParser(subparser):
    """Return the create arg parser.

    Args:
       subparser: argparse.ArgumentParser that is attached to main acloud cmd.

    Returns:
        argparse.ArgumentParser with create options defined.
    """
    create_parser = subparser.add_parser(CMD_CREATE)
    create_parser.required = False
    create_parser.set_defaults(which=CMD_CREATE)
    create_parser.add_argument(
        "--local-instance",
        action="store_true",
        dest="local_instance",
        required=False,
        help="Create a local instance of the AVD.")
    create_parser.add_argument(
        "--avd-type",
        type=str,
        dest="avd_type",
        default=constants.TYPE_CF,
        choices=[constants.TYPE_GCE, constants.TYPE_CF, constants.TYPE_GF],
        help="Android Virtual Device type (default %s)." % constants.TYPE_CF)
    create_parser.add_argument(
        "--flavor",
        type=str,
        dest="flavor",
        default=constants.FLAVOR_PHONE,
        choices=constants.ALL_FLAVORS,
        help="The device flavor of the AVD (default %s)." % constants.FLAVOR_PHONE)
    create_parser.add_argument(
        "--build-target",
        type=str,
        dest="build_target",
        help="Android build target, e.g. aosp_cf_x86_phone-userdebug, "
             "or short names: phone, tablet, or tablet_mobile.")
    create_parser.add_argument(
        "--branch",
        type=str,
        dest="branch",
        help="Android branch, e.g. mnc-dev or git_mnc-dev")
    create_parser.add_argument(
        "--build-id",
        type=str,
        dest="build_id",
        help="Android build id, e.g. 2145099, P2804227")
    create_parser.add_argument(
        "--kernel-build-id",
        type=str,
        dest="kernel_build_id",
        required=False,
        help="Android kernel build id, e.g. 4586590. This is to test a new"
        " kernel build with a particular Android build (--build_id). If not"
        " specified, the kernel that's bundled with the Android build would"
        " be used.")
    create_parser.add_argument(
        "--local-image",
        type=str,
        dest="local_image",
        nargs="?",
        default="",
        required=False,
        help="Use the locally built image for the AVD. Look for the image "
        "artifact in $ANDROID_TARGET_OUT unless a path is specified.")
    create_parser.add_argument(
        "--image-download-dir",
        type=str,
        dest="image_download_dir",
        required=False,
        help="Define remote image download directory, e.g. /usr/local/dl.")
    # User should not specify --spec and --hw_property at the same time.
    hw_spec_group = create_parser.add_mutually_exclusive_group()
    hw_spec_group.add_argument(
        "--hw-property",
        type=str,
        dest="hw_property",
        required=False,
        help="Supported HW properties and example values: %s" %
        constants.HW_PROPERTIES_CMD_EXAMPLE)
    hw_spec_group.add_argument(
        "--spec",
        type=str,
        dest="spec",
        required=False,
        choices=constants.SPEC_NAMES,
        help="The name of a pre-configured device spec that we are "
        "going to use.")

    AddCommonCreateArgs(create_parser)
    return create_parser


def VerifyArgs(args):
    """Verify args.

    Args:
        args: Namespace object from argparse.parse_args.

    Raises:
        errors.CreateError: Path doesn't exist.
    """
    if args.local_image and not os.path.exists(args.local_image):
        raise errors.CheckPathError(
            "Specified path doesn't exist: %s" % args.local_image)

    hw_properties = create_common.ParseHWPropertyArgs(args.hw_property)
    for key in hw_properties:
        if key not in constants.HW_PROPERTIES:
            raise errors.InvalidHWPropertyError(
                "[%s] is an invalid hw property, supported values are:%s. "
                % (key, constants.HW_PROPERTIES))
