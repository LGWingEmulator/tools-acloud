# Copyright 2019 - The Android Open Source Project
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
r"""GceLocalImageRemoteInstance class.

Create class that is responsible for creating a gce remote instance AVD with a
local image.
"""

import logging
import os

from acloud import errors
from acloud.create import base_avd_create
from acloud.internal.lib import utils
from acloud.public import device_driver

_GCE_LOCAL_IMAGE_CANDIDATE = ["avd-system.tar.gz",
                              "android_system_disk_syslinux.img"]

logger = logging.getLogger(__name__)


class GceLocalImageRemoteInstance(base_avd_create.BaseAVDCreate):
    """Create class for a gce local image remote instance AVD."""

    @utils.TimeExecute(function_description="Total time: ",
                       print_before_call=False, print_status=False)
    def _CreateAVD(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.

        Returns:
            A Report instance.
        """
        local_image_path = self._GetGceLocalImagePath(avd_spec.local_image_dir)
        logger.info("GCE local image: %s", local_image_path)

        report = device_driver.CreateAndroidVirtualDevices(
            avd_spec.cfg,
            num=avd_spec.num,
            local_disk_image=local_image_path,
            autoconnect=avd_spec.autoconnect,
            report_internal_ip=avd_spec.report_internal_ip,
            avd_spec=avd_spec)

        # Launch vnc client if we're auto-connecting.
        if avd_spec.autoconnect:
            utils.LaunchVNCFromReport(report, avd_spec)

        return report


    @staticmethod
    def _GetGceLocalImagePath(local_image_dir):
        """Get gce local image path.

        If local_image_dir is dir, prioritize find avd-system.tar.gz;
        otherwise, find android_system_disk_syslinux.img.

        Args:
            local_image_dir: A string to specify local image dir.

        Returns:
            String, image file path if exists.

        Raises:
            errors.BootImgDoesNotExist if image not exist.
        """
        if os.path.isfile(local_image_dir):
            return local_image_dir

        for img_name in _GCE_LOCAL_IMAGE_CANDIDATE:
            full_file_path = os.path.join(local_image_dir, img_name)
            if os.path.exists(full_file_path):
                return full_file_path

        raise errors.BootImgDoesNotExist("Could not find any GCE images (%s), "
                                         "you can build them via \"m dist\"" %
                                         ", ".join(_GCE_LOCAL_IMAGE_CANDIDATE))
