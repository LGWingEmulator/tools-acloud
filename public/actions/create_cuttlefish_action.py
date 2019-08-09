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

"""Create cuttlefish instances.

TODO: This module now just contains the skeleton but not the actual logic.
      Need to fill in the actuall logic.
"""

import logging

from acloud.public.actions import common_operations
from acloud.public.actions import base_device_factory
from acloud.internal import constants
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.internal.lib import cvd_compute_client
from acloud.internal.lib import cvd_compute_client_multi_stage


logger = logging.getLogger(__name__)


class CuttlefishDeviceFactory(base_device_factory.BaseDeviceFactory):
    """A class that can produce a cuttlefish device.

    Attributes:
        cfg: An AcloudConfig instance.
        build_target: String,Target name.
        build_id: String, Build id, e.g. "2263051", "P2804227"
        kernel_build_id: String, Kernel build id.
        avd_spec: An AVDSpec instance.

    """

    LOG_FILES = ["/home/vsoc-01/cuttlefish_runtime/kernel.log",
                 "/home/vsoc-01/cuttlefish_runtime/logcat",
                 "/home/vsoc-01/cuttlefish_runtime/cuttlefish_config.json"]

    def __init__(self, cfg, build_target, build_id, branch=None,
                 kernel_build_id=None, avd_spec=None, kernel_branch=None,
                 kernel_build_target=None, system_branch=None,
                 system_build_id=None, system_build_target=None):

        self.credentials = auth.CreateCredentials(cfg)

        if cfg.enable_multi_stage:
            compute_client = cvd_compute_client_multi_stage.CvdComputeClient(
                cfg, self.credentials)
        else:
            compute_client = cvd_compute_client.CvdComputeClient(
                cfg, self.credentials)
        super(CuttlefishDeviceFactory, self).__init__(compute_client)

        # Private creation parameters
        self._cfg = cfg
        self._build_target = build_target
        self._build_id = build_id
        self._branch = branch
        self._kernel_build_id = kernel_build_id
        self._blank_data_disk_size_gb = cfg.extra_data_disk_size_gb
        self._avd_spec = avd_spec
        self._extra_scopes = cfg.extra_scopes

        # Configure clients for interaction with GCE/Build servers
        self._build_client = android_build_client.AndroidBuildClient(
            self.credentials)

        # Get build_info namedtuple for platform, kernel, system build
        self.build_info = self._build_client.GetBuildInfo(
            build_target, build_id, branch)
        self.kernel_build_info = self._build_client.GetBuildInfo(
            kernel_build_target or cfg.kernel_build_target, kernel_build_id,
            kernel_branch)
        self.system_build_info = self._build_client.GetBuildInfo(
            system_build_target or build_target, system_build_id, system_branch)

    def GetBuildInfoDict(self):
        """Get build info dictionary.

        Returns:
          A build info dictionary.
        """
        build_info_dict = {
            key: val for key, val in self.build_info.__dict__.items() if val}

        build_info_dict.update(
            {"kernel_%s" % key: val
             for key, val in self.kernel_build_info.__dict__.items() if val}
        )
        build_info_dict.update(
            {"system_%s" % key: val
             for key, val in self.system_build_info.__dict__.items() if val}
        )
        return build_info_dict

    @staticmethod
    def _GetGcsBucketBuildId(build_id, release_id):
        """Get GCS Bucket Build Id.

        Args:
          build_id: The incremental build id. For example 5325535.
          release_id: The release build id, None if not a release build.
                      For example AAAA.190220.001.

        Returns:
          GCS bucket build id. For example: AAAA.190220.001-5325535
        """
        return "-".join([release_id, build_id]) if release_id else build_id

    def CreateInstance(self):
        """Creates singe configured cuttlefish device.

        Override method from parent class.

        Returns:
            A string, representing instance name.
        """

        # Create host instances for cuttlefish device. Currently one host instance
        # has one cuttlefish device. In the future, these logics should be modified
        # to support multiple cuttlefish devices per host instance.
        instance = self._compute_client.GenerateInstanceName(
            build_id=self.build_info.build_id, build_target=self._build_target)

        # Create an instance from Stable Host Image
        self._compute_client.CreateInstance(
            instance=instance,
            image_name=self._cfg.stable_host_image_name,
            image_project=self._cfg.stable_host_image_project,
            build_target=self.build_info.build_target,
            branch=self.build_info.branch,
            build_id=self._GetGcsBucketBuildId(
                self.build_info.build_id, self.build_info.release_build_id),
            kernel_branch=self.kernel_build_info.branch,
            kernel_build_id=self.kernel_build_info.build_id,
            kernel_build_target=self.kernel_build_info.build_target,
            blank_data_disk_size_gb=self._blank_data_disk_size_gb,
            avd_spec=self._avd_spec,
            extra_scopes=self._extra_scopes,
            system_build_target=self.system_build_info.build_target,
            system_branch=self.system_build_info.branch,
            system_build_id=self._GetGcsBucketBuildId(
                self.system_build_info.build_id,
                self.system_build_info.release_build_id))

        return instance


#pylint: disable=too-many-locals
def CreateDevices(avd_spec=None,
                  cfg=None,
                  build_target=None,
                  build_id=None,
                  branch=None,
                  kernel_build_id=None,
                  kernel_branch=None,
                  kernel_build_target=None,
                  system_branch=None,
                  system_build_id=None,
                  system_build_target=None,
                  num=1,
                  serial_log_file=None,
                  logcat_file=None,
                  autoconnect=False,
                  report_internal_ip=False,
                  boot_timeout_secs=None):
    """Create one or multiple Cuttlefish devices.

    Args:
        avd_spec: An AVDSpec instance.
        cfg: An AcloudConfig instance.
        build_target: String, Target name.
        build_id: String, Build id, e.g. "2263051", "P2804227"
        branch: Branch name, a string, e.g. aosp_master
        kernel_build_id: String, Kernel build id.
        kernel_branch: String, Kernel branch name.
        kernel_build_target: String, Kernel build target name.
        system_branch: Branch name to consume the system.img from, a string.
        system_build_id: System branch build id, a string.
        system_build_target: System image build target, a string.
        num: Integer, Number of devices to create.
        serial_log_file: String, A path to a tar file where serial output should
                         be saved to.
        logcat_file: String, A path to a file where logcat logs should be saved.
        autoconnect: Boolean, Create ssh tunnel(s) and adb connect after device creation.
        report_internal_ip: Boolean to report the internal ip instead of
                            external ip.
        boot_timeout_secs: Integer, the maximum time in seconds used to
                               wait for the AVD to boot.

    Returns:
        A Report instance.
    """
    client_adb_port = None
    if avd_spec:
        cfg = avd_spec.cfg
        build_target = avd_spec.remote_image[constants.BUILD_TARGET]
        build_id = avd_spec.remote_image[constants.BUILD_ID]
        num = avd_spec.num
        autoconnect = avd_spec.autoconnect
        report_internal_ip = avd_spec.report_internal_ip
        serial_log_file = avd_spec.serial_log_file
        logcat_file = avd_spec.logcat_file
        client_adb_port = avd_spec.client_adb_port
        boot_timeout_secs = avd_spec.boot_timeout_secs
        kernel_branch = avd_spec.kernel_build_info[constants.BUILD_BRANCH]
        kernel_build_id = avd_spec.kernel_build_info[constants.BUILD_ID]
        kernel_build_target = avd_spec.kernel_build_info[constants.BUILD_TARGET]
        system_branch = avd_spec.system_build_info[constants.BUILD_BRANCH]
        system_build_id = avd_spec.system_build_info[constants.BUILD_ID]
        system_build_target = avd_spec.system_build_info[constants.BUILD_TARGET]
    logger.info(
        "Creating a cuttlefish device in project %s, "
        "build_target: %s, "
        "build_id: %s, "
        "branch: %s, "
        "kernel_build_id: %s, "
        "kernel_branch: %s, "
        "kernel_build_target: %s, "
        "system_branch: %s, "
        "system_build_id: %s, "
        "system_build_target: %s, "
        "num: %s, "
        "serial_log_file: %s, "
        "logcat_file: %s, "
        "autoconnect: %s, "
        "report_internal_ip: %s", cfg.project, build_target,
        build_id, branch, kernel_build_id, kernel_branch, kernel_build_target,
        system_branch, system_build_id, system_build_target, num,
        serial_log_file, logcat_file, autoconnect, report_internal_ip)
    device_factory = CuttlefishDeviceFactory(
        cfg, build_target, build_id, branch=branch, avd_spec=avd_spec,
        kernel_build_id=kernel_build_id, kernel_branch=kernel_branch,
        kernel_build_target=kernel_build_target, system_branch=system_branch,
        system_build_id=system_build_id,
        system_build_target=system_build_target)
    return common_operations.CreateDevices("create_cf", cfg, device_factory,
                                           num, constants.TYPE_CF,
                                           report_internal_ip, autoconnect,
                                           serial_log_file, logcat_file,
                                           client_adb_port, boot_timeout_secs)
