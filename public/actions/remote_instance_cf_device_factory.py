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

"""RemoteInstanceDeviceFactory provides basic interface to create a cuttlefish
device factory."""

from distutils.spawn import find_executable
import glob
import logging
import os
import subprocess

from acloud.internal import constants
from acloud.internal.lib import auth
from acloud.internal.lib import cvd_compute_client
from acloud.internal.lib import cvd_compute_client_multi_stage
from acloud.internal.lib import utils
from acloud.public.actions import base_device_factory


logger = logging.getLogger(__name__)

_CMD_LAUNCH_CVD_ARGS = ("-cpus %s -x_res %s -y_res %s -dpi %s "
                        "-memory_mb %s ")
_CMD_LAUNCH_CVD_DISK_ARGS = ("-blank_data_image_mb %s "
                             "-data_policy always_create ")

#Output to Serial port 1 (console) group in the instance
_OUTPUT_CONSOLE_GROUPS = "tty"
SSH_BIN = "ssh"
_SSH_CMD = (" -i %(rsa_key_file)s "
            "-q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "
            "-l %(login_user)s %(ip_addr)s ")
_SSH_CMD_MAX_RETRY = 2
_SSH_CMD_RETRY_SLEEP = 3
_USER_BUILD = "userbuild"


class RemoteInstanceDeviceFactory(base_device_factory.BaseDeviceFactory):
    """A class that can produce a cuttlefish device.

    Attributes:
        avd_spec: AVDSpec object that tells us what we're going to create.
        cfg: An AcloudConfig instance.
        local_image_artifact: A string, path to local image.
        cvd_host_package_artifact: A string, path to cvd host package.
        report_internal_ip: Boolean, True for the internal ip is used when
                            connecting from another GCE instance.
        credentials: An oauth2client.OAuth2Credentials instance.
        compute_client: An object of cvd_compute_client.CvdComputeClient.
        ssh_cmd: Sting, ssh command to connect GCE instance.
    """
    def __init__(self, avd_spec, local_image_artifact, cvd_host_package_artifact):
        """Constructs a new remote instance device factory."""
        self._avd_spec = avd_spec
        self._cfg = avd_spec.cfg
        self._local_image_artifact = local_image_artifact
        self._cvd_host_package_artifact = cvd_host_package_artifact
        self._report_internal_ip = avd_spec.report_internal_ip
        self.credentials = auth.CreateCredentials(avd_spec.cfg)
        # Control compute_client with enable_multi_stage
        if self._cfg.enable_multi_stage:
            compute_client = cvd_compute_client_multi_stage.CvdComputeClient(
                avd_spec.cfg, self.credentials)
        else:
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
        self._SetAVDenv(constants.GCE_USER)
        self._UploadArtifacts(constants.GCE_USER,
                              self._local_image_artifact,
                              self._cvd_host_package_artifact,
                              self._avd_spec.local_image_dir)
        self._LaunchCvd(constants.GCE_USER, self._avd_spec.hw_property)
        return instance

    @staticmethod
    def _ShellCmdWithRetry(remote_cmd):
        """Runs a shell command on remote device.

        If the network is unstable and causes SSH connect fail, it will retry.
        When it retry in a short time, you may encounter unstable network. We
        will use the mechanism of RETRY_BACKOFF_FACTOR. The retry time for each
        failure is times * retries.

        Args:
            remote_cmd: A string, shell command to be run on remote.

        Raises:
            subprocess.CalledProcessError: For any non-zero return code of
                                           remote_cmd.

        Returns:
            Boolean, True if the command was successfully executed. False otherwise.
        """
        return utils.RetryExceptionType(
            exception_types=subprocess.CalledProcessError,
            max_retries=_SSH_CMD_MAX_RETRY,
            functor=lambda cmd: subprocess.check_call(cmd, shell=True),
            sleep_multiplier=_SSH_CMD_RETRY_SLEEP,
            retry_backoff_factor=utils.DEFAULT_RETRY_BACKOFF_FACTOR,
            cmd=remote_cmd)

    def _CreateGceInstance(self):
        """Create a single configured cuttlefish device.

        Override method from parent class.
        build_target: The format is like "aosp_cf_x86_phone". We only get info
                      from the user build image file name. If the file name is
                      not custom format (no "-"), we will use $TARGET_PRODUCT
                      from environment variable as build_target.

        Returns:
            A string, representing instance name.
        """
        image_name = os.path.basename(
            self._local_image_artifact) if self._local_image_artifact else ""
        build_target = (os.environ.get(constants.ENV_BUILD_TARGET) if "-" not
                        in image_name else image_name.split("-")[0])
        instance = self._compute_client.GenerateInstanceName(
            build_target=build_target, build_id=_USER_BUILD)
        # Create an instance from Stable Host Image
        self._compute_client.CreateInstance(
            instance=instance,
            image_name=self._cfg.stable_host_image_name,
            image_project=self._cfg.stable_host_image_project,
            blank_data_disk_size_gb=self._cfg.extra_data_disk_size_gb,
            avd_spec=self._avd_spec)
        ip = self._compute_client.GetInstanceIP(instance)
        self._ssh_cmd = find_executable(SSH_BIN) + _SSH_CMD % {
            "login_user": constants.GCE_USER,
            "rsa_key_file": self._cfg.ssh_private_key_path,
            "ip_addr": (ip.internal if self._report_internal_ip
                        else ip.external)}
        return instance

    @utils.TimeExecute(function_description="Setting up GCE environment")
    def _SetAVDenv(self, cvd_user):
        """set the user to run AVD in the instance.

        Args:
            cvd_user: A string, user run the cvd in the instance.
        """
        avd_list_of_groups = []
        avd_list_of_groups.extend(constants.LIST_CF_USER_GROUPS)
        avd_list_of_groups.append(_OUTPUT_CONSOLE_GROUPS)
        remote_cmd = ""
        for group in avd_list_of_groups:
            remote_cmd += "\"sudo usermod -aG %s %s;\"" %(group, cvd_user)
        logger.debug("remote_cmd:\n %s", remote_cmd)
        self._ShellCmdWithRetry(self._ssh_cmd + remote_cmd)

    @utils.TimeExecute(function_description="Processing and uploading local images")
    def _UploadArtifacts(self,
                         cvd_user,
                         local_image_zip,
                         cvd_host_package_artifact,
                         images_dir):
        """Upload local images and avd local host package to instance.

        There are two ways to upload local images.
        1. Using local image zip, it would be decompressed by install_zip.sh.
        2. Using local image directory, this directory contains all images.
           Images are compressed/decompressed by lzop during upload process.

        Args:
            cvd_user: String, user upload the artifacts to instance.
            local_image_zip: String, path to zip of local images which
                             build from 'm dist'.
            cvd_host_package_artifact: String, path to cvd host package.
            images_dir: String, directory of local images which build
                        from 'm'.
        """
        # TODO(b/133461252) Deprecate acloud create with local image zip.
        # Upload local image zip file
        if local_image_zip:
            remote_cmd = ("\"sudo su -c '/usr/bin/install_zip.sh .' - '%s'\" < %s"
                          % (cvd_user, local_image_zip))
            logger.debug("remote_cmd:\n %s", remote_cmd)
            self._ShellCmdWithRetry(self._ssh_cmd + remote_cmd)
        else:
            # Compress image files for faster upload.
            artifact_files = [os.path.basename(image) for image in glob.glob(
                os.path.join(images_dir, "*.img"))]
            cmd = ("tar -cf - --lzop -S -C {images_dir} {artifact_files} | "
                   "{ssh_cmd} -- tar -xf - --lzop -S".format(
                       images_dir=images_dir,
                       artifact_files=" ".join(artifact_files),
                       ssh_cmd=self._ssh_cmd))
            logger.debug("cmd:\n %s", cmd)
            self._ShellCmdWithRetry(cmd)

        # host_package
        remote_cmd = ("\"sudo su -c 'tar -x -z -f -' - '%s'\" < %s" %
                      (cvd_user, cvd_host_package_artifact))
        logger.debug("remote_cmd:\n %s", remote_cmd)
        self._ShellCmdWithRetry(self._ssh_cmd + remote_cmd)

    def _LaunchCvd(self, cvd_user, hw_property):
        """Launch CVD.

        Args:
            cvd_user: A string, user run the cvd in the instance.
            hw_property: dict object of hw property.
        """
        launch_cvd_args = _CMD_LAUNCH_CVD_ARGS % (
            hw_property["cpu"],
            hw_property["x_res"],
            hw_property["y_res"],
            hw_property["dpi"],
            hw_property["memory"])
        if constants.HW_ALIAS_DISK in hw_property:
            launch_cvd_args = (launch_cvd_args + _CMD_LAUNCH_CVD_DISK_ARGS %
                               hw_property[constants.HW_ALIAS_DISK])
        remote_cmd = ("\"sudo su -c 'bin/launch_cvd %s>&/dev/ttyS0&' - '%s'\"" %
                      (launch_cvd_args, cvd_user))
        logger.debug("remote_cmd:\n %s", remote_cmd)
        subprocess.Popen(self._ssh_cmd + remote_cmd, shell=True)
