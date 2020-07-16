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
local image. For launching multiple local instances under the same user,
The cuttlefish tool requires 3 variables:
- ANDROID_HOST_OUT: To locate the launch_cvd tool.
- HOME: To specify the temporary folder of launch_cvd.
- CUTTLEFISH_INSTANCE: To specify the instance id.
Acloud user must either set ANDROID_HOST_OUT or run acloud with --local-tool.
Acloud sets the other 2 variables for each local instance.

The adb port and vnc port of local instance will be decided according to
instance id. The rule of adb port will be '6520 + [instance id] - 1' and the vnc
port will be '6444 + [instance id] - 1'.
e.g:
If instance id = 3 the adb port will be 6522 and vnc port will be 6446.

To delete the local instance, we will call stop_cvd with the environment variable
[CUTTLEFISH_CONFIG_FILE] which is pointing to the runtime cuttlefish json.
"""

import logging
import os
import shutil
import subprocess
import threading
import sys

from acloud import errors
from acloud.create import base_avd_create
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.internal.lib.adb_tools import AdbTools
from acloud.list import list as list_instance
from acloud.list import instance
from acloud.public import report


logger = logging.getLogger(__name__)

_CMD_LAUNCH_CVD_ARGS = (" -daemon -cpus %s -x_res %s -y_res %s -dpi %s "
                        "-memory_mb %s -run_adb_connector=%s "
                        "-system_image_dir %s -instance_dir %s "
                        "-undefok=report_anonymous_usage_stats,enable_sandbox "
                        "-report_anonymous_usage_stats=y "
                        "-enable_sandbox=false")
_CMD_LAUNCH_CVD_GPU_ARG = " -gpu_mode=drm_virgl"
_CMD_LAUNCH_CVD_DISK_ARGS = (" -blank_data_image_mb %s "
                             "-data_policy always_create")
_CMD_LAUNCH_CVD_WEBRTC_ARGS = (" -guest_enforce_security=false "
                               "-vm_manager=crosvm "
                               "-start_webrtc=true "
                               "-webrtc_public_ip=%s" % constants.LOCALHOST)

# In accordance with the number of network interfaces in
# /etc/init.d/cuttlefish-common
_MAX_INSTANCE_ID = 10

_INSTANCES_IN_USE_MSG = ("All instances are in use. Try resetting an instance "
                         "by specifying --local-instance and an id between 1 "
                         "and %d." % _MAX_INSTANCE_ID)
_CONFIRM_RELAUNCH = ("\nCuttlefish AVD[id:%d] is already running. \n"
                     "Enter 'y' to terminate current instance and launch a new "
                     "instance, enter anything else to exit out[y/N]: ")


class LocalImageLocalInstance(base_avd_create.BaseAVDCreate):
    """Create class for a local image local instance AVD."""

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
        # Running instances on local is not supported on all OS.
        if not utils.IsSupportedPlatform(print_warning=True):
            result_report = report.Report(command="create")
            result_report.SetStatus(report.Status.FAIL)
            return result_report

        local_image_path, host_bins_path = self.GetImageArtifactsPath(avd_spec)

        # Determine the instance id.
        if avd_spec.local_instance_id:
            ins_id = avd_spec.local_instance_id
            ins_lock = instance.GetLocalInstanceLock(ins_id)
            if not ins_lock.Lock():
                result_report = report.Report(command="create")
                result_report.AddError("Instance %d is locked by another "
                                       "process." % ins_id)
                result_report.SetStatus(report.Status.FAIL)
                return result_report
        else:
            ins_id = None
            for candidate_id in range(1, _MAX_INSTANCE_ID + 1):
                ins_lock = instance.GetLocalInstanceLock(candidate_id)
                if ins_lock.LockIfNotInUse(timeout_secs=0):
                    ins_id = candidate_id
                    break
            if not ins_id:
                result_report = report.Report(command="create")
                result_report.AddError(_INSTANCES_IN_USE_MSG)
                result_report.SetStatus(report.Status.FAIL)
                return result_report
            logger.info("Selected instance id: %d", ins_id)

        try:
            if not self._CheckRunningCvd(ins_id, no_prompts):
                # Mark as in-use so that it won't be auto-selected again.
                ins_lock.SetInUse(True)
                sys.exit(constants.EXIT_BY_USER)

            result_report = self._CreateInstance(ins_id, local_image_path,
                                                 host_bins_path, avd_spec,
                                                 no_prompts)
            # The infrastructure is able to delete the instance only if the
            # instance name is reported. This method changes the state to
            # in-use after creating the report.
            ins_lock.SetInUse(True)
            return result_report
        finally:
            ins_lock.Unlock()

    def _CreateInstance(self, local_instance_id, local_image_path,
                        host_bins_path, avd_spec, no_prompts):
        """Create a CVD instance.

        Args:
            local_instance_id: Integer of instance id.
            local_image_path: String of local image directory.
            host_bins_path: String of host package directory.
            avd_spec: AVDSpec for the instance.
            no_prompts: Boolean, True to skip all prompts.

        Returns:
            A Report instance.
        """
        if avd_spec.connect_webrtc:
            utils.ReleasePort(constants.WEBRTC_LOCAL_PORT)

        launch_cvd_path = os.path.join(host_bins_path, "bin",
                                       constants.CMD_LAUNCH_CVD)
        cmd = self.PrepareLaunchCVDCmd(launch_cvd_path,
                                       avd_spec.hw_property,
                                       avd_spec.connect_adb,
                                       local_image_path,
                                       local_instance_id,
                                       avd_spec.connect_webrtc,
                                       avd_spec.gpu)

        result_report = report.Report(command="create")
        instance_name = instance.GetLocalInstanceName(local_instance_id)
        try:
            self._LaunchCvd(cmd, local_instance_id, host_bins_path,
                            (avd_spec.boot_timeout_secs or
                             constants.DEFAULT_CF_BOOT_TIMEOUT))
        except errors.LaunchCVDFail as launch_error:
            result_report.SetStatus(report.Status.BOOT_FAIL)
            result_report.AddDeviceBootFailure(
                instance_name, constants.LOCALHOST, None, None,
                error=str(launch_error))
            return result_report

        active_ins = list_instance.GetActiveCVD(local_instance_id)
        if active_ins:
            result_report.SetStatus(report.Status.SUCCESS)
            result_report.AddDevice(instance_name, constants.LOCALHOST,
                                    active_ins.adb_port, active_ins.vnc_port)
            # Launch vnc client if we're auto-connecting.
            if avd_spec.connect_vnc:
                utils.LaunchVNCFromReport(result_report, avd_spec, no_prompts)
            if avd_spec.connect_webrtc:
                utils.LaunchBrowserFromReport(result_report)
            if avd_spec.unlock_screen:
                AdbTools(active_ins.adb_port).AutoUnlockScreen()
        else:
            err_msg = "cvd_status return non-zero after launch_cvd"
            logger.error(err_msg)
            result_report.SetStatus(report.Status.BOOT_FAIL)
            result_report.AddDeviceBootFailure(
                instance_name, constants.LOCALHOST, None, None, error=err_msg)
        return result_report

    @staticmethod
    def _FindCvdHostBinaries(search_paths):
        """Return the directory that contains CVD host binaries."""
        for search_path in search_paths:
            if os.path.isfile(os.path.join(search_path, "bin",
                                           constants.CMD_LAUNCH_CVD)):
                return search_path

        host_out_dir = os.environ.get(constants.ENV_ANDROID_HOST_OUT)
        if (host_out_dir and
                os.path.isfile(os.path.join(host_out_dir, "bin",
                                            constants.CMD_LAUNCH_CVD))):
            return host_out_dir

        raise errors.GetCvdLocalHostPackageError(
            "CVD host binaries are not found. Please run `make hosttar`, or "
            "set --local-tool to an extracted CVD host package.")

    def GetImageArtifactsPath(self, avd_spec):
        """Get image artifacts path.

        This method will check if launch_cvd is exist and return the tuple path
        (image path and host bins path) where they are located respectively.
        For remote image, RemoteImageLocalInstance will override this method and
        return the artifacts path which is extracted and downloaded from remote.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.

        Returns:
            Tuple of (local image file, host bins package) paths.
        """
        return (avd_spec.local_image_dir,
                self._FindCvdHostBinaries(avd_spec.local_tool_dirs))

    @staticmethod
    def PrepareLaunchCVDCmd(launch_cvd_path, hw_property, connect_adb,
                            system_image_dir, local_instance_id, connect_webrtc,
                            gpu):
        """Prepare launch_cvd command.

        Create the launch_cvd commands with all the required args and add
        in the user groups to it if necessary.

        Args:
            launch_cvd_path: String of launch_cvd path.
            hw_property: dict object of hw property.
            system_image_dir: String of local images path.
            connect_adb: Boolean flag that enables adb_connector.
            local_instance_id: Integer of instance id.
            connect_webrtc: Boolean of connect_webrtc.
            gpu: String of gpu name, the gpu name of local instance should be
                 "default" if gpu is enabled.

        Returns:
            String, launch_cvd cmd.
        """
        instance_dir = instance.GetLocalInstanceRuntimeDir(local_instance_id)
        launch_cvd_w_args = launch_cvd_path + _CMD_LAUNCH_CVD_ARGS % (
            hw_property["cpu"], hw_property["x_res"], hw_property["y_res"],
            hw_property["dpi"], hw_property["memory"],
            ("true" if connect_adb else "false"), system_image_dir,
            instance_dir)
        if constants.HW_ALIAS_DISK in hw_property:
            launch_cvd_w_args = (launch_cvd_w_args + _CMD_LAUNCH_CVD_DISK_ARGS %
                                 hw_property[constants.HW_ALIAS_DISK])
        if connect_webrtc:
            launch_cvd_w_args = launch_cvd_w_args + _CMD_LAUNCH_CVD_WEBRTC_ARGS

        if gpu:
            launch_cvd_w_args = launch_cvd_w_args + _CMD_LAUNCH_CVD_GPU_ARG

        launch_cmd = utils.AddUserGroupsToCmd(launch_cvd_w_args,
                                              constants.LIST_CF_USER_GROUPS)
        logger.debug("launch_cvd cmd:\n %s", launch_cmd)
        return launch_cmd

    @staticmethod
    def _CheckRunningCvd(local_instance_id, no_prompts=False):
        """Check if launch_cvd with the same instance id is running.

        Args:
            local_instance_id: Integer of instance id.
            no_prompts: Boolean, True to skip all prompts.

        Returns:
            Whether the user wants to continue.
        """
        # Check if the instance with same id is running.
        existing_ins = list_instance.GetActiveCVD(local_instance_id)
        if existing_ins:
            if no_prompts or utils.GetUserAnswerYes(_CONFIRM_RELAUNCH %
                                                    local_instance_id):
                existing_ins.Delete()
            else:
                return False
        return True

    @staticmethod
    @utils.TimeExecute(function_description="Waiting for AVD(s) to boot up")
    def _LaunchCvd(cmd, local_instance_id, host_bins_path, timeout=None):
        """Execute Launch CVD.

        Kick off the launch_cvd command and log the output.

        Args:
            cmd: String, launch_cvd command.
            local_instance_id: Integer of instance id.
            host_bins_path: String of host package directory.
            timeout: Integer, the number of seconds to wait for the AVD to boot up.

        Raises:
            errors.LaunchCVDFail when any CalledProcessError.
        """
        # Delete the cvd home/runtime temp if exist. The runtime folder is
        # under the cvd home dir, so we only delete them from home dir.
        cvd_home_dir = instance.GetLocalInstanceHomeDir(local_instance_id)
        cvd_runtime_dir = instance.GetLocalInstanceRuntimeDir(local_instance_id)
        shutil.rmtree(cvd_home_dir, ignore_errors=True)
        os.makedirs(cvd_runtime_dir)

        cvd_env = os.environ.copy()
        # launch_cvd assumes host bins are in $ANDROID_HOST_OUT.
        cvd_env[constants.ENV_ANDROID_HOST_OUT] = host_bins_path
        cvd_env[constants.ENV_CVD_HOME] = cvd_home_dir
        cvd_env[constants.ENV_CUTTLEFISH_INSTANCE] = str(local_instance_id)
        # Check the result of launch_cvd command.
        # An exit code of 0 is equivalent to VIRTUAL_DEVICE_BOOT_COMPLETED
        process = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT,
                                   env=cvd_env)
        if timeout:
            timer = threading.Timer(timeout, process.kill)
            timer.start()
        process.wait()
        if timeout:
            timer.cancel()
        if process.returncode == 0:
            return
        raise errors.LaunchCVDFail(
            "Can't launch cuttlefish AVD. Return code:%s. \nFor more detail: "
            "%s/launcher.log" % (str(process.returncode), cvd_runtime_dir))
