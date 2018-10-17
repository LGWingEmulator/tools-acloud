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
r"""BaseAVDCreate class.

Parent class that will hold common logic for AVD creation use cases.
"""

from __future__ import print_function
from distutils.spawn import find_executable
import logging
import os
import subprocess
import sys

from acloud.internal import constants
from acloud.internal.lib import utils

logger = logging.getLogger(__name__)

_VNC_BIN = "ssvnc"
_CMD_START_VNC = "%(bin)s vnc://127.0.01:%(port)d"
_CMD_INSTALL_SSVNC = "sudo apt-get --assume-yes install ssvnc"
_ENV_DISPLAY = "DISPLAY"
_SSVNC_ENV_VARS = {"SSVNC_NO_ENC_WARN":"1", "SSVNC_SCALE":"auto"}

_CONFIRM_CONTINUE = ("In order to display the screen to the AVD, we'll need to "
                     "install a vnc client (ssnvc). \nWould you like acloud to "
                     "install it for you? (%s) \nPress 'y' to continue or "
                     "anything else to abort it:[y]") % _CMD_INSTALL_SSVNC


class BaseAVDCreate(object):
    """Base class for all AVD intance creation classes."""

    # pylint: disable=no-self-use
    def Create(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
        """
        raise NotImplementedError

    def LaunchVncClient(self, port=constants.DEFAULT_VNC_PORT):
        """Launch ssvnc.

        Args:
            port: Integer, port number.
        """
        try:
            os.environ[_ENV_DISPLAY]
        except KeyError:
            utils.PrintColorString("Remote terminal can't support VNC. "
                                   "Skipping VNC startup.",
                                   utils.TextColors.FAIL)
            return

        if not find_executable(_VNC_BIN):
            if utils.GetUserAnswerYes(_CONFIRM_CONTINUE):
                try:
                    print("Installing ssvnc vnc client... ", end="")
                    sys.stdout.flush()
                    subprocess.check_output(_CMD_INSTALL_SSVNC, shell=True)
                    utils.PrintColorString("Done", utils.TextColors.OKGREEN)
                except subprocess.CalledProcessError as cpe:
                    utils.PrintColorString("Failed to install ssvnc: %s" %
                                           cpe.output, utils.TextColors.FAIL)
                    return
            else:
                return
        ssvnc_env = os.environ.copy()
        ssvnc_env.update(_SSVNC_ENV_VARS)
        ssvnc_args = _CMD_START_VNC % {"bin":find_executable(_VNC_BIN), "port":port}
        subprocess.Popen(ssvnc_args.split(), env=ssvnc_env)

    def PrintAvdDetails(self, avd_spec):
        """Display spec information to user.

        Example:
            Creating remote AVD instance with the following details:
            Image:
              aosp/master - aosp_cf_x86_phone-userdebug [1234]
            hw config:
              cpu - 2
              ram - 2GB
              disk - 10GB
              display - 1024x862 (224 DPI)

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
        """
        print("Creating %s AVD instance with the following details:" % avd_spec.instance_type)
        if avd_spec.image_source == constants.IMAGE_SRC_LOCAL:
            print("Image (local):")
            print("  %s" % avd_spec.local_image_dir)
        elif avd_spec.image_source == constants.IMAGE_SRC_REMOTE:
            print("Image:")
            print("  %s - %s [%s]" % (avd_spec.remote_image[constants.BUILD_BRANCH],
                                      avd_spec.remote_image[constants.BUILD_TARGET],
                                      avd_spec.remote_image[constants.BUILD_ID]))
        print("hw config:")
        print("  cpu - %s" % (avd_spec.hw_property[constants.HW_ALIAS_CPUS]))
        print("  ram - %dGB" % (
            int(avd_spec.hw_property[constants.HW_ALIAS_MEMORY]) / 1024))
        print("  disk - %dGB" % (
            int(avd_spec.hw_property[constants.HW_ALIAS_DISK]) / 1024))
        print("  display - %sx%s (%s DPI)" % (avd_spec.hw_property[constants.HW_X_RES],
                                              avd_spec.hw_property[constants.HW_Y_RES],
                                              avd_spec.hw_property[constants.HW_ALIAS_DPI]))
        print("\n")
