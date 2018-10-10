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
import time

from acloud import errors
from acloud.create import base_avd_create
from acloud.create import create_common
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.setup import host_setup_runner

logger = logging.getLogger(__name__)

_BOOT_COMPLETE = "VIRTUAL_DEVICE_BOOT_COMPLETED"
_CMD_LAUNCH_CVD = "launch_cvd"
# TODO(b/117366819): Currently --serial_number is not working.
_CMD_LAUNCH_CVD_ARGS = (" --daemon --cpus %s --x_res %s --y_res %s --dpi %s "
                        "--memory_mb %s --blank_data_image_mb %s "
                        "--data_policy always_create "
                        "--system_image_dir %s "
                        "--vnc_server_port %s "
                        "--serial_number %s")
_CMD_PGREP = "pgrep"
_CMD_SG = "sg "
_CMD_STOP_CVD = "stop_cvd"
_CONFIRM_RELAUNCH = ("\nCuttlefish AVD is already running. \nPress 'y' to "
                     "terminate current instance and launch new instance \nor "
                     "anything else to exit out.")
_CVD_SERIAL_PREFIX = "acloudCF"
_ENV_ANDROID_HOST_OUT = "ANDROID_HOST_OUT"


class LocalImageLocalInstance(base_avd_create.BaseAVDCreate):
    """Create class for a local image local instance AVD."""

    def Create(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
        """
        self.PrintAvdDetails(avd_spec)
        start = time.time()

        local_image_path, launch_cvd_path = self.GetImageArtifactsPath(avd_spec)

        cmd = self.PrepareLaunchCVDCmd(launch_cvd_path,
                                       avd_spec.hw_property,
                                       local_image_path,
                                       avd_spec.flavor)
        try:
            self.CheckLaunchCVD(cmd)
        except errors.LaunchCVDFail as launch_error:
            raise launch_error

        utils.PrintColorString("\n")
        utils.PrintColorString("Total time: %ds" % (time.time() - start),
                               utils.TextColors.WARNING)
        # TODO(b/117366819): Should display the correct device serial
        # according to the args --serial_number.
        utils.PrintColorString("Device serial: %s:%s" %
                               (constants.LOCALHOST_ADB_SERIAL,
                                constants.DEFAULT_ADB_PORT),
                               utils.TextColors.WARNING)
        if avd_spec.autoconnect:
            self.LaunchVncClient()


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
            os.environ.get(_ENV_ANDROID_HOST_OUT), "bin", _CMD_LAUNCH_CVD)
        if not os.path.exists(launch_cvd_path):
            raise errors.GetCvdLocalHostPackageError(
                "No launch_cvd found. Please run \"m launch_cvd\" first")

        return avd_spec.local_image_dir, launch_cvd_path

    @staticmethod
    def PrepareLaunchCVDCmd(launch_cvd_path, hw_property, system_image_dir,
                            flavor):
        """Prepare launch_cvd command.

        Combine whole launch_cvd cmd including the hw property options and login
        as the required groups if need. The reason using here-doc instead of
        ampersand sign is all operations need to be ran in ths same pid.
        The example of cmd:
        $ sg kvm  << EOF
        sg libvirt
        sg cvdnetwork
        launch_cvd --cpus 2 --x_res 1280 --y_res 720 --dpi 160 --memory_mb 4096
        EOF

        Args:
            launch_cvd_path: String of launch_cvd path.
            hw_property: dict object of hw property.
            system_image_dir: String of local images path.
            flavor: String of flavor type.

        Returns:
            String, launch_cvd cmd.
        """
        launch_cvd_w_args = launch_cvd_path + _CMD_LAUNCH_CVD_ARGS % (
            hw_property["cpu"], hw_property["x_res"], hw_property["y_res"],
            hw_property["dpi"], hw_property["memory"], hw_property["disk"],
            system_image_dir, constants.DEFAULT_VNC_PORT,
            _CVD_SERIAL_PREFIX+flavor)

        combined_launch_cmd = ""
        host_setup = host_setup_runner.CuttlefishHostSetup()
        if not host_setup.CheckUserInGroups(constants.LIST_CF_USER_GROUPS):
            # As part of local host setup to enable local instance support,
            # the user is added to certain groups. For those settings to
            # take effect systemwide requires the user to log out and
            # log back in. In the scenario where the user has run setup and
            # hasn't logged out, we still want them to be able to launch a
            # local instance so add the user to the groups as part of the
            # command to ensure success.
            logger.debug("User group is not ready for cuttlefish")
            for idx, group in enumerate(constants.LIST_CF_USER_GROUPS):
                combined_launch_cmd += _CMD_SG + group
                if idx == 0:
                    combined_launch_cmd += " <<EOF\n"
                else:
                    combined_launch_cmd += "\n"
            launch_cvd_w_args += "\nEOF"

        combined_launch_cmd += launch_cvd_w_args
        logger.debug("launch_cvd cmd:\n %s", combined_launch_cmd)
        return combined_launch_cmd

    def CheckLaunchCVD(self, cmd):
        """Execute launch_cvd command and wait for boot up completed.

        Args:
            cmd: String, launch_cvd command.
        """
        start = time.time()

        # Cuttlefish support launch single AVD at one time currently.
        if self._IsLaunchCVDInUse():
            logger.info("Cuttlefish AVD is already running.")
            if utils.GetUserAnswerYes(_CONFIRM_RELAUNCH):
                stop_cvd_cmd = os.path.join(os.environ.get(_ENV_ANDROID_HOST_OUT),
                                            "bin", _CMD_STOP_CVD)
                subprocess.check_output(stop_cvd_cmd)
            else:
                print("Only 1 cuttlefish AVD at a time, "
                      "please stop the current AVD via #acloud delete")
                return

        utils.PrintColorString("Waiting for AVD to boot... ",
                               utils.TextColors.WARNING, end="")

        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)

        boot_complete = False
        for line in iter(process.stdout.readline, b''):
            logger.debug(line.strip())
            # cvd is still running and got boot complete.
            if _BOOT_COMPLETE in line:
                utils.PrintColorString("OK! (%ds)" % (time.time() - start),
                                       utils.TextColors.OKGREEN)
                boot_complete = True
                break

        if not boot_complete:
            utils.PrintColorString("Fail!", utils.TextColors.WARNING)
            raise errors.LaunchCVDFail(
                "Can't launch cuttlefish AVD. No %s found" % _BOOT_COMPLETE)

    @staticmethod
    def _IsLaunchCVDInUse():
        """Check if launch_cvd is running.

        Returns:
            Boolean, True if launch_cvd is running. False otherwise.
        """
        try:
            subprocess.check_output([_CMD_PGREP, _CMD_LAUNCH_CVD])
            return True
        except subprocess.CalledProcessError:
            # launch_cvd process is not in use.
            return False
