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
r"""
Welcome to
   ___  _______   ____  __  _____
  / _ |/ ___/ /  / __ \/ / / / _ \
 / __ / /__/ /__/ /_/ / /_/ / // /
/_/ |_\___/____/\____/\____/____/


This a tool to create Android Virtual Devices locally/remotely.

- Prerequisites:
 The manual will be available at
 https://android.googlesource.com/platform/tools/acloud/+/master/README.md

- To get started:
 - Create instances:
    1) To create a remote cuttlefish instance with the local built image.
       Example:
       $ acloud create --local_image /tmp/image_dir
    2) To create a local cuttlefish instance using the image which has been
       built out in your workspace.
       Example:
       $ acloud create --local-instance --local-image

 - Delete instances:
   $ acloud delete

Try $acloud [cmd] --help for further details.

"""
import argparse
import getpass
import logging
import sys

# Needed to silence oauth2client.
# This is a workaround to get rid of below warning message:
# 'No handlers could be found for logger "oauth2client.contrib.multistore_file'
# TODO(b/112803893): Remove this code once bug is fixed.
OAUTH2_LOGGER = logging.getLogger('oauth2client.contrib.multistore_file')
OAUTH2_LOGGER.setLevel(logging.CRITICAL)
OAUTH2_LOGGER.addHandler(logging.FileHandler("/dev/null"))

# pylint: disable=wrong-import-position
from acloud.create import create
from acloud.create import create_args
from acloud.delete import delete
from acloud.delete import delete_args
from acloud.internal import constants
from acloud.metrics import metrics
from acloud.public import acloud_common
from acloud.public import config
from acloud.public import device_driver
from acloud.public import errors
from acloud.public.actions import create_cuttlefish_action
from acloud.public.actions import create_goldfish_action
from acloud.setup import setup
from acloud.setup import setup_args

LOGGING_FMT = "%(asctime)s |%(levelname)s| %(module)s:%(lineno)s| %(message)s"
ACLOUD_LOGGER = "acloud"

# Commands
CMD_CREATE_CUTTLEFISH = "create_cf"
CMD_CREATE_GOLDFISH = "create_gf"
CMD_DELETE = "delete"
CMD_CLEANUP = "cleanup"
CMD_SSHKEY = "project_sshkey"


# pylint: disable=too-many-statements
def _ParseArgs(args):
    """Parse args.

    Args:
        args: Argument list passed from main.

    Returns:
        Parsed args.
    """
    usage = ",".join([
        setup_args.CMD_SETUP,
        create_args.CMD_CREATE,
        CMD_CREATE_CUTTLEFISH,
        CMD_CREATE_GOLDFISH,
        delete_args.CMD_DELETE,
    ])
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="acloud {" + usage + "} ...")
    subparsers = parser.add_subparsers()
    subparser_list = []

    # Command "create_cf", create cuttlefish instances
    create_cf_parser = subparsers.add_parser(CMD_CREATE_CUTTLEFISH)
    create_cf_parser.required = False
    create_cf_parser.set_defaults(which=CMD_CREATE_CUTTLEFISH)
    create_cf_parser.add_argument(
        "--build_target",
        type=str,
        dest="build_target",
        help="Android build target, should be a cuttlefish target name.")
    create_cf_parser.add_argument(
        "--branch",
        type=str,
        dest="branch",
        help="Android branch, e.g. git_master")
    create_cf_parser.add_argument(
        "--build_id",
        type=str,
        dest="build_id",
        help="Android build id, e.g. 2145099, P2804227")
    create_cf_parser.add_argument(
        "--kernel_build_id",
        type=str,
        dest="kernel_build_id",
        required=False,
        help="Android kernel build id, e.g. 4586590. This is to test a new"
        " kernel build with a particular Android build (--build_id). If not"
        " specified, the kernel that's bundled with the Android build would"
        " be used.")

    create_args.AddCommonCreateArgs(create_cf_parser)
    subparser_list.append(create_cf_parser)

    # Command "create_gf", create goldfish instances
    # In order to create a goldfish device we need the following parameters:
    # 1. The emulator build we wish to use, this is the binary that emulates
    #    an android device. See go/emu-dev for more
    # 2. A system-image. This is the android release we wish to run on the
    #    emulated hardware.
    create_gf_parser = subparsers.add_parser(CMD_CREATE_GOLDFISH)
    create_gf_parser.required = False
    create_gf_parser.set_defaults(which=CMD_CREATE_GOLDFISH)
    create_gf_parser.add_argument(
        "--build_target",
        type=str,
        dest="build_target",
        help="Android build target, should be a goldfish target name.")
    create_gf_parser.add_argument(
        "--branch",
        type=str,
        dest="branch",
        help="Android branch, e.g. git_master")
    create_gf_parser.add_argument(
        "--build_id",
        type=str,
        dest="build_id",
        help="Android build id, e.g. 4669424, P2804227")
    create_gf_parser.add_argument(
        "--emulator_build_id",
        type=str,
        dest="emulator_build_id",
        required=False,
        help="Emulator build used to run the images. e.g. 4669466.")
    create_gf_parser.add_argument(
        "--gpu",
        type=str,
        dest="gpu",
        required=False,
        default=None,
        help="GPU accelerator to use if any."
        " e.g. nvidia-tesla-k80, omit to use swiftshader")
    create_gf_parser.add_argument(
        "--base_image",
        type=str,
        dest="base_image",
        required=False,
        help="Name of the goldfish base image to be used to create the instance. "
        "This will override stable_goldfish_host_image_name from config. "
        "e.g. emu-dev-cts-061118")

    create_args.AddCommonCreateArgs(create_gf_parser)
    subparser_list.append(create_gf_parser)

    # Command "cleanup"
    cleanup_parser = subparsers.add_parser(CMD_CLEANUP)
    cleanup_parser.required = False
    cleanup_parser.set_defaults(which=CMD_CLEANUP)
    cleanup_parser.add_argument(
        "--expiration_mins",
        type=int,
        dest="expiration_mins",
        required=True,
        help="Garbage collect all gce instances, gce images, cached disk "
        "images that are older than |expiration_mins|.")
    subparser_list.append(cleanup_parser)

    # Command "project_sshkey"
    sshkey_parser = subparsers.add_parser(CMD_SSHKEY)
    sshkey_parser.required = False
    sshkey_parser.set_defaults(which=CMD_SSHKEY)
    sshkey_parser.add_argument(
        "--user",
        type=str,
        dest="user",
        default=getpass.getuser(),
        help="The user name which the sshkey belongs to, default to: %s." %
        getpass.getuser())
    sshkey_parser.add_argument(
        "--ssh_rsa_path",
        type=str,
        dest="ssh_rsa_path",
        required=True,
        help="Absolute path to the file that contains the public rsa key "
        "that will be added as project-wide ssh key.")
    subparser_list.append(sshkey_parser)

    # Command "create"
    subparser_list.append(create_args.GetCreateArgParser(subparsers))

    # Command "setup"
    subparser_list.append(setup_args.GetSetupArgParser(subparsers))

    # Command "Delete"
    subparser_list.append(delete_args.GetDeleteArgParser(subparsers))

    # Add common arguments.
    for subparser in subparser_list:
        acloud_common.AddCommonArguments(subparser)

    return parser.parse_args(args)


# pylint: disable=too-many-branches
def _VerifyArgs(parsed_args):
    """Verify args.

    Args:
        parsed_args: Parsed args.

    Raises:
        errors.CommandArgError: If args are invalid.
    """
    if parsed_args.which == create_args.CMD_CREATE:
        create_args.VerifyArgs(parsed_args)

    if (parsed_args.which == create_args.CMD_CREATE
            and parsed_args.avd_type == constants.TYPE_GCE):
        if (parsed_args.spec and parsed_args.spec not in constants.SPEC_NAMES):
            raise errors.CommandArgError(
                "%s is not valid. Choose from: %s" %
                (parsed_args.spec, ", ".join(constants.SPEC_NAMES)))
        if not ((parsed_args.build_id and parsed_args.build_target)
                or parsed_args.gce_image or parsed_args.local_disk_image):
            raise errors.CommandArgError(
                "At least one of the following should be specified: "
                "--build_id and --build_target, or --gce_image, or "
                "--local_disk_image.")
        if bool(parsed_args.build_id) != bool(parsed_args.build_target):
            raise errors.CommandArgError(
                "Must specify --build_id and --build_target at the same time.")

    if parsed_args.which == CMD_CREATE_CUTTLEFISH:
        if not parsed_args.build_id or not parsed_args.build_target:
            raise errors.CommandArgError(
                "Must specify --build_id and --build_target")

    if parsed_args.which == CMD_CREATE_GOLDFISH:
        if not parsed_args.emulator_build_id and not parsed_args.build_id:
            raise errors.CommandArgError("Must specify either "
                                         "--emulator_build_id or --build_id")
        if not parsed_args.build_target:
            raise errors.CommandArgError("Must specify --build_target")

    if parsed_args.which in [
            create_args.CMD_CREATE, CMD_CREATE_CUTTLEFISH, CMD_CREATE_GOLDFISH
    ]:
        if (parsed_args.serial_log_file
                and not parsed_args.serial_log_file.endswith(".tar.gz")):
            raise errors.CommandArgError(
                "--serial_log_file must ends with .tar.gz")
        if (parsed_args.logcat_file
                and not parsed_args.logcat_file.endswith(".tar.gz")):
            raise errors.CommandArgError(
                "--logcat_file must ends with .tar.gz")


def _SetupLogging(log_file, verbose):
    """Setup logging.

    This function define the logging policy in below manners.
    - without -v , -vv ,--log_file:
    Only display critical log and print() message on screen.

    - with -v:
    Display INFO log and set StreamHandler to acloud parent logger to turn on
    ONLY acloud modules logging.(silence all 3p libraries)

    - with -vv:
    Display INFO/DEBUG log and set StreamHandler to root logger to turn on all
    acloud modules and 3p libraries logging.

    - with --log_file.
    Dump logs to FileHandler with DEBUG level.

    Args:
        log_file: String, if not None, dump the log to log file.
        verbose: Int, if verbose = 1(-v), log at INFO level and turn on
                 logging on libraries to a StreamHandler.
                 If verbose = 2(-vv), log at DEBUG level and turn on logging on
                 all libraries and 3rd party libraries to a StreamHandler.
    """
    # Define logging level and hierarchy by verbosity.
    shandler_level = None
    logger = None
    if verbose == 0:
        shandler_level = logging.CRITICAL
        logger = logging.getLogger(ACLOUD_LOGGER)
    elif verbose == 1:
        shandler_level = logging.INFO
        logger = logging.getLogger(ACLOUD_LOGGER)
    elif verbose > 1:
        shandler_level = logging.DEBUG
        logger = logging.getLogger()

    # Add StreamHandler by default.
    shandler = logging.StreamHandler()
    shandler.setFormatter(logging.Formatter(LOGGING_FMT))
    shandler.setLevel(shandler_level)
    logger.addHandler(shandler)
    # Set the default level to DEBUG, the other handlers will handle
    # their own levels via the args supplied (-v and --log_file).
    logger.setLevel(logging.DEBUG)

    # Add FileHandler if log_file is provided.
    if log_file:
        fhandler = logging.FileHandler(filename=log_file)
        fhandler.setFormatter(logging.Formatter(LOGGING_FMT))
        fhandler.setLevel(logging.DEBUG)
        logger.addHandler(fhandler)


def main(argv):
    """Main entry.

    Args:
        argv: A list of system arguments.

    Returns:
        0 if success. None-zero if fails.
    """
    args = _ParseArgs(argv)
    _SetupLogging(args.log_file, args.verbose)
    _VerifyArgs(args)

    cfg = config.GetAcloudConfig(args)
    # TODO: Move this check into the functions it is actually needed.
    # Check access.
    # device_driver.CheckAccess(cfg)

    metrics.LogUsage()
    report = None
    if (args.which == create_args.CMD_CREATE
            and args.avd_type == constants.TYPE_GCE):
        report = device_driver.CreateAndroidVirtualDevices(
            cfg,
            args.build_target,
            args.build_id,
            args.num,
            args.gce_image,
            args.local_disk_image,
            cleanup=not args.no_cleanup,
            serial_log_file=args.serial_log_file,
            logcat_file=args.logcat_file,
            autoconnect=args.autoconnect,
            report_internal_ip=args.report_internal_ip)
    elif args.which == create_args.CMD_CREATE:
        create.Run(args)
    elif args.which == CMD_CREATE_CUTTLEFISH:
        report = create_cuttlefish_action.CreateDevices(
            cfg=cfg,
            build_target=args.build_target,
            build_id=args.build_id,
            kernel_build_id=args.kernel_build_id,
            num=args.num,
            serial_log_file=args.serial_log_file,
            logcat_file=args.logcat_file,
            autoconnect=args.autoconnect,
            report_internal_ip=args.report_internal_ip)
    elif args.which == CMD_CREATE_GOLDFISH:
        report = create_goldfish_action.CreateDevices(
            cfg=cfg,
            build_target=args.build_target,
            build_id=args.build_id,
            emulator_build_id=args.emulator_build_id,
            gpu=args.gpu,
            num=args.num,
            serial_log_file=args.serial_log_file,
            logcat_file=args.logcat_file,
            autoconnect=args.autoconnect,
            branch=args.branch,
            report_internal_ip=args.report_internal_ip)
    elif args.which == CMD_DELETE:
        report = delete.Run(args)
    elif args.which == CMD_CLEANUP:
        report = device_driver.Cleanup(cfg, args.expiration_mins)
    elif args.which == CMD_SSHKEY:
        report = device_driver.AddSshRsa(cfg, args.user, args.ssh_rsa_path)
    elif args.which == setup_args.CMD_SETUP:
        setup.Run(args)
    else:
        sys.stderr.write("Invalid command %s" % args.which)
        return 2

    if report:
        report.Dump(args.report_file)
        if report.errors:
            msg = "\n".join(report.errors)
            sys.stderr.write("Encountered the following errors:\n%s\n" % msg)
            return 1
    return 0


if __name__ == "__main__":
    main(sys.argv[1:])
