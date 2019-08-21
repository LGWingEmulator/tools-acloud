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
"""A client that manages Cuttlefish Virtual Device on compute engine.

** CvdComputeClient **

CvdComputeClient derives from AndroidComputeClient. It manges a google
compute engine project that is setup for running Cuttlefish Virtual Devices.
It knows how to create a host instance from Cuttlefish Stable Host Image, fetch
Android build, and start Android within the host instance.

** Class hierarchy **

  base_cloud_client.BaseCloudApiClient
                ^
                |
       gcompute_client.ComputeClient
                ^
                |
       android_compute_client.AndroidComputeClient
                ^
                |
       cvd_compute_client_multi_stage.CvdComputeClient

"""

import logging
import os
import stat
import subprocess
import tempfile
import threading

from distutils.spawn import find_executable
from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import android_build_client
from acloud.internal.lib import android_compute_client
from acloud.internal.lib import gcompute_client
from acloud.internal.lib import utils

logger = logging.getLogger(__name__)

_DEFAULT_BRANCH = "aosp-master"
_GCE_USER = "vsoc-01"
_FETCHER_BUILD_TARGET = "aosp_cf_x86_phone-userdebug"
_FETCHER_NAME = "fetch_cvd"
_SSH_BIN = "ssh"
_SSH_CMD = (" -i %(rsa_key_file)s "
            "-q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no "
            "-l %(login_user)s %(ip_addr)s ")
_SSH_CMD_MAX_RETRY = 4
_SSH_CMD_RETRY_SLEEP = 3


def _ProcessBuild(build_id=None, branch=None, build_target=None):
    """Create a Cuttlefish fetch_cvd build string.

    Args:
        build_id: A specific build number to load from. Takes precedence over `branch`.
        branch: A manifest-branch at which to get the latest build.
        build_target: A particular device to load at the desired build.

    Returns:
        A string, used in the fetch_cvd cmd or None if all args are None.
    """
    if not build_target:
        return build_id or branch
    elif build_target and not branch:
        branch = _DEFAULT_BRANCH
    return (build_id or branch) + "/" + build_target


def _SshLogOutput(cmd, timeout=None):
    """Runs a single SSH command while logging its output and processes its return code.

    Output is streamed to the log at the debug level for more interactive debugging.
    SSH returns error code 255 for "failed to connect", so this is interpreted as a failure in
    SSH rather than a failure on the target device and this is converted to a different exception
    type.

    Args:
        cmd: String the full SSH command to run, including the SSH binary and its arguments.
        timeout: Optional integer, number of seconds to give

    Raises:
        errors.DeviceConnectionError: Failed to connect to the GCE instance.
        subprocess.CalledProc: The process exited with an error on the instance.
    """
    logger.info("Running command \"%s\"", cmd)
    # This code could use check_output instead, but this construction supports
    # streaming the logs as they are received.
    process = subprocess.Popen(cmd, shell=True, stdin=None,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if timeout:
        timer = threading.Timer(timeout, process.kill)
        timer.start()
    while True:
        output = process.stdout.readline()
        # poll() can return "0" for success, None means it is still running.
        if output == '' and process.poll() is not None:
            break
        if output:
            # fetch_cvd and launch_cvd can be noisy, so left at debug
            logger.debug(output.strip())
    if timeout:
        timer.cancel()
    process.stdout.close()
    if process.returncode == 255:
        raise errors.DeviceConnectionError(
            "Failed to send command to instance (%s)" % cmd)
    elif process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)


class CvdComputeClient(android_compute_client.AndroidComputeClient):
    """Client that manages Android Virtual Device."""

    DATA_POLICY_CREATE_IF_MISSING = "create_if_missing"

    def __init__(self, acloud_config, oauth2_credentials):
        """Initialize.

        Args:
            acloud_config: An AcloudConfig object.
            oauth2_credentials: An oauth2client.OAuth2Credentials instance.
        """
        super(CvdComputeClient, self).__init__(acloud_config, oauth2_credentials)

        self._fetch_cvd_version = acloud_config.fetch_cvd_version
        self._build_api = (
            android_build_client.AndroidBuildClient(oauth2_credentials))
        self._ssh_private_key_path = acloud_config.ssh_private_key_path
        self._instance_to_args = dict()
        self._instance_to_ip = dict()

    def WaitForBoot(self, instance, boot_timeout_secs=None):
        """Optionally initiates the boot, then waits for the boot to complete.

        For the local-image use case, the local image wrapper code will already launch the device
        so for parity this will not attempt to launch it in the local-image case.

        For the remote-image case, because this knows the files are present and unlaunched it will
        run "launch_cvd -daemon" which exits when the device has successfully booted.

        Args:
            instance: String, name of instance.
            boot_timeout_secs: Integer, the maximum time in seconds used to
                               wait for the AVD to boot.
        Returns:
            True if devcie bootup successful.
        """
        if instance in self._instance_to_args:
            ssh_command = "./bin/launch_cvd -daemon " + " ".join(self._instance_to_args[instance])
            self.SshCommand(self._instance_to_ip[instance], ssh_command, boot_timeout_secs)
            return True
        return super(CvdComputeClient, self).WaitForBoot(instance, boot_timeout_secs)

    # pylint: disable=arguments-differ,too-many-locals
    def CreateInstance(self, instance, image_name, image_project,
                       build_target=None, branch=None, build_id=None,
                       kernel_branch=None, kernel_build_id=None,
                       kernel_build_target=None, blank_data_disk_size_gb=None,
                       avd_spec=None, extra_scopes=None,
                       system_build_target=None, system_branch=None,
                       system_build_id=None):

        """Create a single configured cuttlefish device.
        1. Create gcp instance.
        2. Put fetch_cvd on the instance.
        3. Invoke fetch_cvd to fetch and run the instance.

        Args:
            instance: instance name.
            image_name: A string, the name of the GCE image.
            image_project: A string, name of the project where the image lives.
                           Assume the default project if None.
            build_target: Target name, e.g. "aosp_cf_x86_phone-userdebug"
            branch: Branch name, e.g. "aosp-master"
            build_id: Build id, a string, e.g. "2263051", "P2804227"
            kernel_branch: Kernel branch name, e.g. "kernel-common-android-4.14"
            kernel_build_id: Kernel build id, a string, e.g. "223051", "P280427"
            kernel_build_target: String, Kernel build target name.
            blank_data_disk_size_gb: Size of the blank data disk in GB.
            avd_spec: An AVDSpec instance.
            extra_scopes: A list of extra scopes to be passed to the instance.
            system_build_target: Target name for the system image,
                                e.g. "cf_x86_phone-userdebug"
            system_branch: A String, branch name for the system image.
            system_build_id: A string, build id for the system image.

        Returns:
            A string, representing instance name.
        """

        # A blank data disk would be created on the host. Make sure the size of
        # the boot disk is large enough to hold it.
        boot_disk_size_gb = (
            int(self.GetImage(image_name, image_project)["diskSizeGb"]) +
            blank_data_disk_size_gb)

        ip = self._CreateGceInstance(instance, image_name, image_project,
                                     extra_scopes, boot_disk_size_gb, avd_spec)

        self._WaitForSsh(ip)

        if avd_spec:
            return instance

        # TODO: Remove following code after create_cf deprecated.
        self.UpdateFetchCvd(ip)

        self.FetchBuild(ip, build_id, branch, build_target, system_build_id,
                        system_branch, system_build_target, kernel_build_id,
                        kernel_branch, kernel_build_target)

        launch_cvd_args = []

        if blank_data_disk_size_gb > 0:
            # Policy 'create_if_missing' would create a blank userdata disk if
            # missing. If already exist, reuse the disk.
            launch_cvd_args.append(
                "-data_policy=" + self.DATA_POLICY_CREATE_IF_MISSING)
            launch_cvd_args.append(
                "-blank_data_image_mb=%d" % (blank_data_disk_size_gb * 1024))
        if avd_spec:
            launch_cvd_args.append(
                "-x_res=" + avd_spec.hw_property[constants.HW_X_RES])
            launch_cvd_args.append(
                "-y_res=" + avd_spec.hw_property[constants.HW_Y_RES])
            launch_cvd_args.append(
                "-dpi=" + avd_spec.hw_property[constants.HW_ALIAS_DPI])
            if constants.HW_ALIAS_DISK in avd_spec.hw_property:
                launch_cvd_args.append(
                    "-data_policy=" + self.DATA_POLICY_CREATE_IF_MISSING)
                launch_cvd_args.append(
                    "-blank_data_image_mb="
                    + avd_spec.hw_property[constants.HW_ALIAS_DISK])
            if constants.HW_ALIAS_CPUS in avd_spec.hw_property:
                launch_cvd_args.append("-cpus=%s" % avd_spec.hw_property[constants.HW_ALIAS_CPUS])
            if constants.HW_ALIAS_MEMORY in avd_spec.hw_property:
                launch_cvd_args.append(
                    "-memory_mb=%s" % avd_spec.hw_property[constants.HW_ALIAS_MEMORY])
        else:
            resolution = self._resolution.split("x")
            launch_cvd_args.append("-x_res=" + resolution[0])
            launch_cvd_args.append("-y_res=" + resolution[1])
            launch_cvd_args.append("-dpi=" + resolution[3])

        if self._launch_args:
            launch_cvd_args.append(self._launch_args)

        self._instance_to_args[instance] = launch_cvd_args
        self._instance_to_ip[instance] = ip

        return instance

    def GetSshBaseCmd(self, ip):
        """Run a shell command over SSH on a remote instance.

        This will retry the command if it fails from SSH connection errors.

        Args:
            ip: Namedtuple of (internal, external) IP of the instance.

        Returns:
            String of ssh connection command.
        """
        return find_executable(_SSH_BIN) + _SSH_CMD % {
            "login_user": _GCE_USER,
            "rsa_key_file": self._ssh_private_key_path,
            "ip_addr": ip.external}

    @staticmethod
    def ShellCmdWithRetry(remote_cmd, timeout=None):
        """Runs a shell command on remote device.

        If the network is unstable and causes SSH connect fail, it will retry.
        When it retry in a short time, you may encounter unstable network. We
        will use the mechanism of RETRY_BACKOFF_FACTOR. The retry time for each
        failure is times * retries.

        Args:
            remote_cmd: A string, shell command to be run on remote.

        Raises:
            errors.DeviceConnectionError: For any non-zero return code of
                                           remote_cmd.
        """
        utils.RetryExceptionType(
            exception_types=errors.DeviceConnectionError,
            max_retries=_SSH_CMD_MAX_RETRY,
            functor=_SshLogOutput,
            sleep_multiplier=_SSH_CMD_RETRY_SLEEP,
            retry_backoff_factor=utils.DEFAULT_RETRY_BACKOFF_FACTOR,
            cmd=remote_cmd,
            timeout=timeout)

    # TODO(b/117625814): Fix this for cloutop
    def SshCommand(self, ip, target_command, timeout=None):
        """Run a shell command over SSH on a remote instance.

        This will retry the command if it fails from SSH connection errors.

        Args:
            ip: Namedtuple of (internal, external) IP of the instance.
            target_command: String, text of command to run on the remote instance.
            timeout: Integer, the maximum time to wait for the command to respond.
        """
        self.ShellCmdWithRetry(self.GetSshBaseCmd(ip) + target_command, timeout)

    @utils.TimeExecute(function_description="Creating GCE instance")
    def _CreateGceInstance(self, instance, image_name, image_project,
                           extra_scopes, boot_disk_size_gb, avd_spec):
        """Create a single configured cuttlefish device.

        Override method from parent class.
        Args:
            instance: String, instance name.
            image_name: String, the name of the GCE image.
            image_project: String, the name of the project where the image.
            extra_scopes: A list of extra scopes to be passed to the instance.
            boot_disk_size_gb: Integer, size of the boot disk in GB.
            avd_spec: An AVDSpec instance.

        Returns:
            Namedtuple of (internal, external) IP of the instance.
        """
        disk_args = self._GetDiskArgs(
            instance, image_name, image_project, boot_disk_size_gb)

        metadata = self._metadata.copy()

        if avd_spec:
            metadata[constants.INS_KEY_AVD_TYPE] = avd_spec.avd_type
            metadata[constants.INS_KEY_AVD_FLAVOR] = avd_spec.flavor
            metadata[constants.INS_KEY_DISPLAY] = ("%sx%s (%s)" % (
                avd_spec.hw_property[constants.HW_X_RES],
                avd_spec.hw_property[constants.HW_Y_RES],
                avd_spec.hw_property[constants.HW_ALIAS_DPI]))

        disk_args = self._GetDiskArgs(
            instance, image_name, image_project, boot_disk_size_gb)
        gcompute_client.ComputeClient.CreateInstance(
            self,
            instance=instance,
            image_name=image_name,
            image_project=image_project,
            disk_args=disk_args,
            metadata=metadata,
            machine_type=self._machine_type,
            network=self._network,
            zone=self._zone,
            extra_scopes=extra_scopes)
        ip = gcompute_client.ComputeClient.GetInstanceIP(
            self, instance=instance, zone=self._zone)

        return ip

    @utils.TimeExecute(function_description="Waiting for SSH server")
    def _WaitForSsh(self, ip):
        """Wait until the remote instance is ready to accept commands over SSH.

        Args:
            ip: Namedtuple of (internal, external) IP of the instance.
        """
        self.SshCommand(ip, "uptime")

    @utils.TimeExecute(function_description="Uploading build fetcher to instance")
    def UpdateFetchCvd(self, ip):
        """Download fetch_cvd from the Build API, and upload it to a remote instance.

        The version of fetch_cvd to use is retrieved from the configuration file. Once fetch_cvd
        is on the instance, future commands can use it to download relevant Cuttlefish files from
        the Build API on the instance itself.

        Args:
            ip: Namedtuple of (internal, external) IP of the instance.
        """
        # TODO(schuffelen): Support fetch_cvd_version="latest" when there is
        # stronger automated testing on it.
        download_dir = tempfile.mkdtemp()
        download_target = os.path.join(download_dir, _FETCHER_NAME)
        self._build_api.DownloadArtifact(
            build_target=_FETCHER_BUILD_TARGET,
            build_id=self._fetch_cvd_version,
            resource_id=_FETCHER_NAME,
            local_dest=download_target,
            attempt_id="latest")
        fetch_cvd_stat = os.stat(download_target)
        os.chmod(download_target, fetch_cvd_stat.st_mode | stat.S_IEXEC)

        func = lambda rsa, ip: utils.ScpPushFile(
            src_file=download_target,
            dst_file=_FETCHER_NAME,
            host_name=ip.external,
            user_name=_GCE_USER,
            rsa_key_file=rsa)

        utils.RetryExceptionType(
            exception_types=errors.DeviceConnectionError,
            max_retries=_SSH_CMD_MAX_RETRY,
            functor=func,
            sleep_multiplier=_SSH_CMD_RETRY_SLEEP,
            retry_backoff_factor=utils.DEFAULT_RETRY_BACKOFF_FACTOR,
            rsa=self._ssh_private_key_path,
            ip=ip)

        os.remove(download_target)
        os.rmdir(download_dir)

    @utils.TimeExecute(function_description="Downloading build on instance")
    def FetchBuild(self, ip, build_id, branch, build_target, system_build_id,
                   system_branch, system_build_target, kernel_build_id,
                   kernel_branch, kernel_build_target):
        """Execute fetch_cvd on the remote instance to get Cuttlefish runtime files.

        Args:
            ip: Namedtuple of (internal, external) IP of the instance.
            fetch_args: String of arguments to pass to fetch_cvd.
        """
        fetch_cvd_args = ["-credential_source=gce"]

        default_build = _ProcessBuild(build_id, branch, build_target)
        if default_build:
            fetch_cvd_args.append("-default_build=" + default_build)
        system_build = _ProcessBuild(system_build_id, system_branch, system_build_target)
        if system_build:
            fetch_cvd_args.append("-system_build=" + system_build)
        # kernel_target have default value "kernel". If user provide kernel_build_id
        # or kernel_branch, then start to process kernel image.
        if kernel_build_id or kernel_branch:
            kernel_build = _ProcessBuild(kernel_build_id, kernel_branch, kernel_build_target)
            if kernel_build:
                fetch_cvd_args.append("-kernel_build=" + kernel_build)

        self.SshCommand(ip, "./fetch_cvd " + " ".join(fetch_cvd_args))
