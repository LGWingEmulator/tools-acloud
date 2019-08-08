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
r"""LocalImageRemoteInstance class.

Create class that is responsible for creating a remote instance AVD with a
local image.
"""

import logging
import os

from acloud import errors
from acloud.create import base_avd_create
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.public.actions import common_operations
from acloud.public.actions import remote_instance_cf_device_factory


logger = logging.getLogger(__name__)

_CVD_HOST_PACKAGE = "cvd-host_package.tar.gz"


class LocalImageRemoteInstance(base_avd_create.BaseAVDCreate):
    """Create class for a local image remote instance AVD.

    Attributes:
        cvd_host_package_artifact: A string, path to cvd host package.
    """

    def __init__(self):
        """LocalImageRemoteInstance initialize."""
        self.cvd_host_package_artifact = None

    def VerifyHostPackageArtifactsExist(self):
        """Verify the host package exists and return its path.

        Look for the host package in $ANDROID_HOST_OUT and dist dir.

        Return:
            A string, the path to the host package.
        """
        dirs_to_check = filter(None,
                               [os.environ.get(constants.ENV_ANDROID_HOST_OUT)])
        dist_dir = utils.GetDistDir()
        if dist_dir:
            dirs_to_check.append(dist_dir)

        cvd_host_package_artifact = self.GetCvdHostPackage(dirs_to_check)
        logger.debug("cvd host package: %s", cvd_host_package_artifact)
        return cvd_host_package_artifact

    @staticmethod
    def GetCvdHostPackage(paths):
        """Get cvd host package path.

        Args:
            paths: A list, holds the paths to check for the host package.

        Returns:
            String, full path of cvd host package.

        Raises:
            errors.GetCvdLocalHostPackageError: Can't find cvd host package.
        """
        for path in paths:
            cvd_host_package = os.path.join(path, _CVD_HOST_PACKAGE)
            if os.path.exists(cvd_host_package):
                return cvd_host_package
        raise errors.GetCvdLocalHostPackageError, (
            "Can't find the cvd host package (Try lunching a cuttlefish target"
            " like aosp_cf_x86_phone-userdebug and running 'm'): \n%s" %
            '\n'.join(paths))

    @utils.TimeExecute(function_description="Total time: ",
                       print_before_call=False, print_status=False)
    def _CreateAVD(self, avd_spec, no_prompts):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
            no_prompts: Boolean, True to skip all prompts.

        Returns:
            A Report instance.
        """
        self.cvd_host_package_artifact = self.VerifyHostPackageArtifactsExist()
        device_factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            avd_spec,
            avd_spec.local_image_artifact,
            self.cvd_host_package_artifact)
        report = common_operations.CreateDevices(
            "create_cf", avd_spec.cfg, device_factory, avd_spec.num,
            report_internal_ip=avd_spec.report_internal_ip,
            autoconnect=avd_spec.autoconnect,
            avd_type=constants.TYPE_CF,
            boot_timeout_secs=avd_spec.boot_timeout_secs)
        # Launch vnc client if we're auto-connecting.
        if avd_spec.autoconnect:
            utils.LaunchVNCFromReport(report, avd_spec, no_prompts)
        return report
