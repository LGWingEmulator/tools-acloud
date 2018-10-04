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
from acloud.create import create_common
from acloud.create import base_avd_create

logger = logging.getLogger(__name__)

CVD_HOST_PACKAGE = "cvd-host_package.tar.gz"
ENV_ANDROID_BUILD_TOP = "ANDROID_BUILD_TOP"


class LocalImageRemoteInstance(base_avd_create.BaseAVDCreate):
    """Create class for a local image remote instance AVD.

    Attributes:
        local_image_artifact: A string, path to local image.
        cvd_host_package_artifact: A string, path to cvd host package.
    """

    def __init__(self):
        """LocalImageRemoteInstance initialize."""
        self.local_image_artifact = None
        self.cvd_host_package_artifact = None

    def VerifyArtifactsExist(self, local_image_dir):
        """Verify required cuttlefish image artifacts exists."""
        self.local_image_artifact = create_common.VerifyLocalImageArtifactsExist(
            local_image_dir)
        self.cvd_host_package_artifact = self.VerifyHostPackageArtifactsExist(
            local_image_dir)

    def VerifyHostPackageArtifactsExist(self, local_image_dir):
        """Verify the host package exists and return its path.

        Look for the host package in local_image_dir (when we download the
        image artifacts from Android Build into 1 folder), if we can't find
        it, look in the dist dir (if the user built the image locally).

        Args:
            local_image_dir: A string, path to check for the host package.

        Return:
            A string, the path to the host package.
        """
        dist_dir = os.path.join(
            os.environ.get(ENV_ANDROID_BUILD_TOP, "."), "out", "dist")
        cvd_host_package_artifact = self.GetCvdHostPackage(
            [local_image_dir, dist_dir])
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
            cvd_host_package = os.path.join(path, CVD_HOST_PACKAGE)
            if os.path.exists(cvd_host_package):
                return cvd_host_package
        raise errors.GetCvdLocalHostPackageError, (
            "Can't find the cvd host package: \n%s." %
            '\n'.join(paths))

    def Create(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
        """
        print("We will create a remote instance AVD with a local image: %s" %
              avd_spec)
        self.VerifyArtifactsExist(avd_spec.local_image_dir)
