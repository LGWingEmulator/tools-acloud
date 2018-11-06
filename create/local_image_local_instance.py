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
r"""LocalImageLocalInstance class.

Create class that is responsible for creating a local instance AVD with a
local image.
"""

from __future__ import print_function
import logging
import os
import subprocess
import sys

from acloud import errors
from acloud.create import base_avd_create
from acloud.create import create_common
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.public import report
from acloud.setup import host_setup_runner

logger = logging.getLogger(__name__)

_BOOT_COMPLETE = "VIRTUAL_DEVICE_BOOT_COMPLETED"
_CMD_LAUNCH_CVD_ARGS = (" --daemon --cpus %s --x_res %s --y_res %s --dpi %s "
                        "--memory_mb %s --blank_data_image_mb %s "
                        "--data_policy always_create "
                        "--system_image_dir %s "
                        "--vnc_server_port %s")
_CMD_PGREP = "pgrep"
_CMD_SG = "sg "
_CMD_STOP_CVD = "stop_cvd"
_CONFIRM_RELAUNCH = ("\nCuttlefish AVD is already running. \n"
                     "Enter 'y' to terminate current instance and launch a new "
                     "instance, enter anything else to exit out [y]: ")
_ENV_ANDROID_HOST_OUT = "ANDROID_HOST_OUT"


class LocalImageLocalInstance(base_avd_create.BaseAVDCreate):
    """Create class for a local image local instance AVD."""

    @utils.TimeExecute(function_description="Total time: ",
                       print_before_call=False, print_status=False)
    def _CreateAVD(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
        """
        local_image_path, launch_cvd_path = self.GetImageArtifactsPath(avd_spec)

        cmd = self.PrepareLaunchCVDCmd(launch_cvd_path,
                                       avd_spec.hw_property,
                                       local_image_path)
        try:
            self.CheckLaunchCVD(cmd, os.path.dirname(launch_cvd_path))
        except errors.LaunchCVDFail as launch_error:
            raise launch_error

        result_report = report.Report("local")
        result_report.SetStatus(report.Status.SUCCESS)
        result_report.AddData(key="devices",
                              value={"adb_port": constants.DEFAULT_ADB_PORT,
                                     constants.VNC_PORT: constants.DEFAULT_VNC_PORT})
        # Launch vnc client if we're auto-connecting.
        if avd_spec.autoconnect:
            utils.LaunchVNCFromReport(result_report, avd_spec)
        return result_report

    @staticmethod
    def GetImageArtifactsPath(avd_spec):
        """Get image artifacts path.

        This method will check if local image and launch_cvd are exist and
        return the tuple path where they are located respectively.
        For remote image, RemoteImageLocalInstance will override this method and
        return the artifacts path which is extracted and downloaded from remote.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.

        Returns:
            Tuple of (local image file, launch_cvd package) paths.
        """
        try:
            # Check if local image is exist.
            create_common.VerifyLocalImageArtifactsExist(
                avd_spec.local_image_dir)

        # TODO(b/117306227): help user to build out images and host package if
        # anything needed is not found.
        except errors.GetLocalImageError as imgerror:
            logger.error(imgerror.message)
            raise imgerror

        # Check if launch_cvd is exist.
        launch_cvd_path = os.path.join(
            os.environ.get(_ENV_ANDROID_HOST_OUT), "bin", constants.CMD_LAUNCH_CVD)
        if not os.path.exists(launch_cvd_path):
            raise errors.GetCvdLocalHostPackageError(
                "No launch_cvd found. Please run \"m launch_cvd\" first")

        return avd_spec.local_image_dir, launch_cvd_path

    @staticmethod
    def _AddUserGroupsToCmd(cmd):
        """Add the user groups to the command if necessary.

        As part of local host setup to enable local instance support,
        the user is added to certain groups. For those settings to
        take effect systemwide requires the user to log out and
        log back in. In the scenario where the user has run setup and
        hasn't logged out, we still want them to be able to launch a
        local instance so add the user to the groups as part of the
        command to ensure success.

        The reason using here-doc instead of '&' is all operations need to be
        ran in ths same pid.  Here's an example cmd:
        $ sg kvm  << EOF
        sg libvirt
        sg cvdnetwork
        launch_cvd --cpus 2 --x_res 1280 --y_res 720 --dpi 160 --memory_mb 4096
        EOF

        Args:
            cmd: String of the command to prepend the user groups to.

        Returns:
            String of the command with the user groups prepended to it if
            necessary, otherwise the same existing command.
        """
        user_group_cmd = ""
        host_setup = host_setup_runner.CuttlefishHostSetup()
        if not host_setup.CheckUserInGroups(constants.LIST_CF_USER_GROUPS):
            logger.debug("Need to add user groups to the command")
            for idx, group in enumerate(constants.LIST_CF_USER_GROUPS):
                user_group_cmd += _CMD_SG + group
                if idx == 0:
                    user_group_cmd += " <<EOF\n"
                else:
                    user_group_cmd += "\n"
            cmd += "\nEOF"
        user_group_cmd += cmd
        logger.debug("user group cmd: %s", user_group_cmd)
        return user_group_cmd

    def PrepareLaunchCVDCmd(self, launch_cvd_path, hw_property,
                            system_image_dir):
        """Prepare launch_cvd command.

        Create the launch_cvd commands with all the required args and add
        in the user groups to it if necessary.

        Args:
            launch_cvd_path: String of launch_cvd path.
            hw_property: dict object of hw property.
            system_image_dir: String of local images path.

        Returns:
            String, launch_cvd cmd.
        """
        launch_cvd_w_args = launch_cvd_path + _CMD_LAUNCH_CVD_ARGS % (
            hw_property["cpu"], hw_property["x_res"], hw_property["y_res"],
            hw_property["dpi"], hw_property["memory"], hw_property["disk"],
            system_image_dir, constants.DEFAULT_VNC_PORT)

        launch_cmd = self._AddUserGroupsToCmd(launch_cvd_w_args)
        logger.debug("launch_cvd cmd:\n %s", launch_cmd)
        return launch_cmd

    @utils.TimeExecute(function_description="Waiting for AVD(s) to boot up")
    def CheckLaunchCVD(self, cmd, host_pack_dir):
        """Execute launch_cvd command and wait for boot up completed.

        Args:
            cmd: String, launch_cvd command.
            host_pack_dir: String of host package directory.
        """
        # Cuttlefish support launch single AVD at one time currently.
        if self._IsLaunchCVDInUse():
            logger.info("Cuttlefish AVD is already running.")
            if utils.GetUserAnswerYes(_CONFIRM_RELAUNCH):
                stop_cvd_cmd = os.path.join(host_pack_dir, _CMD_STOP_CVD)
                with open(os.devnull, "w") as dev_null:
                    subprocess.check_call(
                        self._AddUserGroupsToCmd(stop_cvd_cmd),
                        stderr=dev_null, stdout=dev_null, shell=True)
            else:
                print("Exiting out")
                sys.exit()

        try:
            # Check the result of launch_cvd command.
            # An exit code of 0 is equivalent to VIRTUAL_DEVICE_BOOT_COMPLETED
            logger.debug(subprocess.check_output(cmd, shell=True,
                                                 stderr=subprocess.STDOUT))
        except subprocess.CalledProcessError as error:
            raise errors.LaunchCVDFail(
                "Can't launch cuttlefish AVD.%s. \nFor more detail: "
                "~/cuttlefish_runtime/launcher.log" % error.message)

    @staticmethod
    def _IsLaunchCVDInUse():
        """Check if launch_cvd is running.

        Returns:
            Boolean, True if launch_cvd is running. False otherwise.
        """
        try:
            with open(os.devnull, "w") as dev_null:
                subprocess.check_call([_CMD_PGREP, constants.CMD_LAUNCH_CVD],
                                      stderr=dev_null, stdout=dev_null)
            return True
        except subprocess.CalledProcessError:
            # launch_cvd process is not in use.
            return False
