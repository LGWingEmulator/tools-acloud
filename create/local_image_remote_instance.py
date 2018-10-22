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

from distutils.spawn import find_executable
import getpass
import logging
import os
import subprocess

from acloud import errors
from acloud.create import create_common
from acloud.create import base_avd_create
from acloud.internal import constants
from acloud.internal.lib import auth
from acloud.internal.lib import cvd_compute_client
from acloud.internal.lib import utils
from acloud.public.actions import base_device_factory
from acloud.public.actions import common_operations

logger = logging.getLogger(__name__)

_ALL_SCOPES = [cvd_compute_client.CvdComputeClient.SCOPE]
_CVD_HOST_PACKAGE = "cvd-host_package.tar.gz"
_CVD_USER = getpass.getuser()
_CMD_LAUNCH_CVD_ARGS = (" -cpus %s -x_res %s -y_res %s -dpi %s "
                        "-memory_mb %s -blank_data_image_mb %s "
                        "-data_policy always_create ")

#Output to Serial port 1 (console) group in the instance
_OUTPUT_CONSOLE_GROUPS = "tty"
SSH_BIN = "ssh"
_SSH_CMD = (" -i %(rsa_key_file)s "
            "-q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "
            "-l %(login_user)s %(ip_addr)s ")

class RemoteInstanceDeviceFactory(base_device_factory.BaseDeviceFactory):
    """A class that can produce a cuttlefish device.

    Attributes:
        avd_spec: AVDSpec object that tells us what we're going to create.
        cfg: An AcloudConfig instance.
        image_path: A string, upload image artifact to instance.
        cvd_host_package: A string, upload host package artifact to instance.
        credentials: An oauth2client.OAuth2Credentials instance.
        compute_client: An object of cvd_compute_client.CvdComputeClient.
    """
    def __init__(self, avd_spec, local_image_artifact, cvd_host_package_artifact):
        """Constructs a new remote instance device factory."""
        self._avd_spec = avd_spec
        self._cfg = avd_spec.cfg
        self._local_image_artifact = local_image_artifact
        self._cvd_host_package_artifact = cvd_host_package_artifact
        self._report_internal_ip = avd_spec.report_internal_ip
        self.credentials = auth.CreateCredentials(avd_spec.cfg, _ALL_SCOPES)
        compute_client = cvd_compute_client.CvdComputeClient(
            avd_spec.cfg, self.credentials)
        super(RemoteInstanceDeviceFactory, self).__init__(compute_client)
        # Private creation parameters
        self._ssh_cmd = None

    def CreateInstance(self):
        """Create a single configured cuttlefish device.

        1. Create gcp instance.
        2. setup the AVD env in the instance.
        3. upload the artifacts to instance.
        4. Launch CVD.

        Returns:
            A string, representing instance name.
        """
        instance = self._CreateGceInstance()
        self._SetAVDenv(_CVD_USER)
        self._UploadArtifacts(_CVD_USER,
                              self._local_image_artifact,
                              self._cvd_host_package_artifact)
        self._LaunchCvd(_CVD_USER, self._avd_spec.hw_property)
        return instance

    def _CreateGceInstance(self):
        """Create a single configured cuttlefish device.

        Override method from parent class.

        Returns:
            A string, representing instance name.
        """
        #TODO(117487673): Grab the build target name from the image name.
        instance = self._compute_client.GenerateInstanceName(
            build_target=self._avd_spec.flavor, build_id="local")
        # Create an instance from Stable Host Image
        self._compute_client.CreateInstance(
            instance=instance,
            image_name=self._cfg.stable_host_image_name,
            image_project=self._cfg.stable_host_image_project,
            blank_data_disk_size_gb=self._cfg.extra_data_disk_size_gb,
            avd_spec=self._avd_spec)
        ip = self._compute_client.GetInstanceIP(instance)
        self._ssh_cmd = find_executable(SSH_BIN) + _SSH_CMD % {
            "login_user": getpass.getuser(),
            "rsa_key_file": self._cfg.ssh_private_key_path,
            "ip_addr": (ip.internal if self._report_internal_ip
                        else ip.external)}
        return instance

    @utils.TimeExecute(function_description="Setup GCE environment")
    def _SetAVDenv(self, cvd_user):
        """set the user to run AVD in the instance."""
        avd_list_of_groups = []
        avd_list_of_groups.extend(constants.LIST_CF_USER_GROUPS)
        avd_list_of_groups.append(_OUTPUT_CONSOLE_GROUPS)
        for group in avd_list_of_groups:
            remote_cmd = "\"sudo usermod -aG %s %s\"" %(group, cvd_user)
            logger.debug("remote_cmd:\n %s", remote_cmd)
            subprocess.check_call(self._ssh_cmd + remote_cmd, shell=True)

    @utils.TimeExecute(function_description="Uploading local image")
    def _UploadArtifacts(self,
                         cvd_user,
                         local_image_artifact,
                         cvd_host_package_artifact):
        """Upload local image and avd local host package to instance."""
        # local image
        remote_cmd = ("\"sudo su -c '/usr/bin/install_zip.sh .' - '%s'\" < %s" %
                      (cvd_user, local_image_artifact))
        logger.debug("remote_cmd:\n %s", remote_cmd)
        subprocess.check_call(self._ssh_cmd + remote_cmd, shell=True)

        # host_package
        remote_cmd = ("\"sudo su -c 'tar -x -z -f -' - '%s'\" < %s" %
                      (cvd_user, cvd_host_package_artifact))
        logger.debug("remote_cmd:\n %s", remote_cmd)
        subprocess.check_call(self._ssh_cmd + remote_cmd, shell=True)

    def _LaunchCvd(self, cvd_user, hw_property):
        """Launch CVD."""
        lunch_cvd_args = _CMD_LAUNCH_CVD_ARGS % (
            hw_property["cpu"],
            hw_property["x_res"],
            hw_property["y_res"],
            hw_property["dpi"],
            hw_property["memory"],
            hw_property["disk"])
        remote_cmd = ("\"sudo su -c 'bin/launch_cvd %s>&/dev/ttyS0&' - '%s'\"" %
                      (lunch_cvd_args, cvd_user))
        logger.debug("remote_cmd:\n %s", remote_cmd)
        subprocess.Popen(self._ssh_cmd + remote_cmd, shell=True)


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
            os.environ.get(constants.ENV_ANDROID_BUILD_TOP, "."), "out", "dist")
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
            cvd_host_package = os.path.join(path, _CVD_HOST_PACKAGE)
            if os.path.exists(cvd_host_package):
                return cvd_host_package
        raise errors.GetCvdLocalHostPackageError, (
            "Can't find the cvd host package: \n%s" %
            '\n'.join(paths))

    @utils.TimeExecute(function_description="Total time: ",
                       print_before_call=False, print_status=False)
    def _CreateAVD(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.
        """
        self.VerifyArtifactsExist(avd_spec.local_image_dir)
        device_factory = RemoteInstanceDeviceFactory(
            avd_spec,
            self.local_image_artifact,
            self.cvd_host_package_artifact)
        report = common_operations.CreateDevices(
            "create_cf", avd_spec.cfg, device_factory, avd_spec.num,
            report_internal_ip=avd_spec.report_internal_ip,
            autoconnect=avd_spec.autoconnect)
        # Launch vnc client if we're auto-connecting.
        if avd_spec.autoconnect:
            utils.LaunchVNCFromReport(report, avd_spec)
        return report
