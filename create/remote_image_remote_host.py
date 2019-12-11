#!/usr/bin/env python
#
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
r"""RemoteImageRemoteHost class.

Create class that is responsible for creating a remote host AVD with a
remote image.
"""

import logging
import os
import shutil
import tempfile

from acloud.create import base_avd_create
from acloud.create import create_common
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.public.actions import common_operations
from acloud.public.actions import remote_instance_cf_device_factory


logger = logging.getLogger(__name__)


@utils.TimeExecute(function_description="Downloading Android Build artifact")
def DownloadAndProcessArtifact(avd_spec, extract_path):
    """Download the CF image artifacts and process them.

    - Download image from the Android Build system, then decompress it.
    - Download cvd host package from the Android Build system.

    Args:
        avd_spec: AVDSpec object that tells us what we're going to create.
        extract_path: String, path to image folder.
    """
    cfg = avd_spec.cfg
    build_id = avd_spec.remote_image[constants.BUILD_ID]
    build_target = avd_spec.remote_image[constants.BUILD_TARGET]

    logger.debug("Extract path: %s", extract_path)
    # Image zip
    remote_image = "%s-img-%s.zip" % (build_target.split('-')[0],
                                      build_id)
    create_common.DownloadRemoteArtifact(
        cfg, build_target, build_id, remote_image, extract_path, decompress=True)
    # Cvd host package
    create_common.DownloadRemoteArtifact(
        cfg, build_target, build_id, constants.CVD_HOST_PACKAGE,
        extract_path)


class RemoteImageRemoteHost(base_avd_create.BaseAVDCreate):
    """Create class for a remote image remote host AVD."""

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
        extract_path = tempfile.mkdtemp()
        DownloadAndProcessArtifact(avd_spec, extract_path)
        device_factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            avd_spec=avd_spec,
            cvd_host_package_artifact=os.path.join(
                extract_path, constants.CVD_HOST_PACKAGE),
            local_image_dir=extract_path)
        report = common_operations.CreateDevices(
            "create_cf", avd_spec.cfg, device_factory, num=1,
            report_internal_ip=avd_spec.report_internal_ip,
            autoconnect=avd_spec.autoconnect,
            avd_type=constants.TYPE_CF,
            boot_timeout_secs=avd_spec.boot_timeout_secs,
            unlock_screen=avd_spec.unlock_screen,
            wait_for_boot=False)
        # Launch vnc client if we're auto-connecting.
        if avd_spec.connect_vnc:
            utils.LaunchVNCFromReport(report, avd_spec, no_prompts)
        shutil.rmtree(extract_path)
        return report
