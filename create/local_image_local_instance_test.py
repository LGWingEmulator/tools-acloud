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
"""Tests for LocalImageLocalInstance."""

import os
import shutil
import subprocess
import unittest
import mock

from acloud import errors
from acloud.create import local_image_local_instance
from acloud.list import instance
from acloud.list import list as list_instance
from acloud.internal import constants
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils


class LocalImageLocalInstanceTest(driver_test_lib.BaseDriverTest):
    """Test LocalImageLocalInstance method."""

    LAUNCH_CVD_CMD_WITH_DISK = """sg group1 <<EOF
sg group2
launch_cvd -daemon -cpus fake -x_res fake -y_res fake -dpi fake -memory_mb fake -run_adb_connector=true -system_image_dir fake_image_dir -instance_dir fake_cvd_dir -undefok=report_anonymous_usage_stats,enable_sandbox -report_anonymous_usage_stats=y -enable_sandbox=false -blank_data_image_mb fake -data_policy always_create
EOF"""

    LAUNCH_CVD_CMD_NO_DISK = """sg group1 <<EOF
sg group2
launch_cvd -daemon -cpus fake -x_res fake -y_res fake -dpi fake -memory_mb fake -run_adb_connector=true -system_image_dir fake_image_dir -instance_dir fake_cvd_dir -undefok=report_anonymous_usage_stats,enable_sandbox -report_anonymous_usage_stats=y -enable_sandbox=false
EOF"""

    LAUNCH_CVD_CMD_NO_DISK_WITH_GPU = """sg group1 <<EOF
sg group2
launch_cvd -daemon -cpus fake -x_res fake -y_res fake -dpi fake -memory_mb fake -run_adb_connector=true -system_image_dir fake_image_dir -instance_dir fake_cvd_dir -undefok=report_anonymous_usage_stats,enable_sandbox -report_anonymous_usage_stats=y -enable_sandbox=false -gpu_mode=drm_virgl
EOF"""

    LAUNCH_CVD_CMD_WITH_WEBRTC = """sg group1 <<EOF
sg group2
launch_cvd -daemon -cpus fake -x_res fake -y_res fake -dpi fake -memory_mb fake -run_adb_connector=true -system_image_dir fake_image_dir -instance_dir fake_cvd_dir -undefok=report_anonymous_usage_stats,enable_sandbox -report_anonymous_usage_stats=y -enable_sandbox=false -guest_enforce_security=false -vm_manager=crosvm -start_webrtc=true -webrtc_public_ip=127.0.0.1
EOF"""

    _EXPECTED_DEVICES_IN_REPORT = [
        {
            "instance_name": "local-instance-1",
            "ip": "127.0.0.1:6520",
            "adb_port": 6520,
            "vnc_port": 6444
        }
    ]

    _EXPECTED_DEVICES_IN_FAILED_REPORT = [
        {
            "instance_name": "local-instance-1",
            "ip": "127.0.0.1"
        }
    ]

    def setUp(self):
        """Initialize new LocalImageLocalInstance."""
        super(LocalImageLocalInstanceTest, self).setUp()
        self.local_image_local_instance = local_image_local_instance.LocalImageLocalInstance()

    # pylint: disable=protected-access
    @mock.patch("acloud.create.local_image_local_instance.utils")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "GetImageArtifactsPath")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "_CheckRunningCvd")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "_CreateInstance")
    def testCreateAVD(self, mock_create, mock_check_running_cvd,
                      mock_get_image, mock_utils):
        """Test _CreateAVD."""
        mock_utils.IsSupportedPlatform.return_value = True
        mock_get_image.return_value = ("/image/path", "/host/bin/path")
        mock_check_running_cvd.return_value = True
        mock_avd_spec = mock.Mock(local_instance_id=0)
        mock_lock = mock.Mock()
        mock_lock.Lock.return_value = True
        mock_lock.LockIfNotInUse.side_effect = (False, True)
        mock_lock.Unlock.return_value = False
        self.Patch(instance, "GetLocalInstanceLock",
                   return_value=mock_lock)

        # Success
        mock_create.return_value = mock.Mock()
        self.local_image_local_instance._CreateAVD(
            mock_avd_spec, no_prompts=True)
        mock_lock.Lock.assert_not_called()
        self.assertEqual(2, mock_lock.LockIfNotInUse.call_count)
        mock_lock.SetInUse.assert_called_once_with(True)
        mock_lock.Unlock.assert_called_once()

        mock_lock.SetInUse.reset_mock()
        mock_lock.LockIfNotInUse.reset_mock()
        mock_lock.Unlock.reset_mock()

        # Failure with no report
        mock_avd_spec.local_instance_id = 1
        mock_create.side_effect = ValueError("unit test")
        with self.assertRaises(ValueError):
            self.local_image_local_instance._CreateAVD(
                mock_avd_spec, no_prompts=True)
        mock_lock.Lock.assert_called_once()
        mock_lock.LockIfNotInUse.assert_not_called()
        mock_lock.SetInUse.assert_not_called()
        mock_lock.Unlock.assert_called_once()

    @mock.patch("acloud.create.local_image_local_instance.utils")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "_LaunchCvd")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "PrepareLaunchCVDCmd")
    def testCreateInstance(self, _mock_prepare, mock_launch_cvd, _mock_utils):
        """Test the report returned by _CreateInstance."""
        self.Patch(instance, "GetLocalInstanceName",
                   return_value="local-instance-1")
        mock_avd_spec = mock.Mock(unlock_screen=False)
        local_ins = mock.Mock(
            adb_port=6520,
            vnc_port=6444
        )
        local_ins.CvdStatus.return_value = True
        self.Patch(instance, "LocalInstance",
                   return_value=local_ins)
        self.Patch(list_instance, "GetActiveCVD",
                   return_value=local_ins)

        # Success
        report = self.local_image_local_instance._CreateInstance(
            1, "/image/path", "/host/bin/path", mock_avd_spec, no_prompts=True)

        self.assertEqual(report.data.get("devices"),
                         self._EXPECTED_DEVICES_IN_REPORT)

        # Failure
        mock_launch_cvd.side_effect = errors.LaunchCVDFail("timeout")

        report = self.local_image_local_instance._CreateInstance(
            1, "/image/path", "/host/bin/path", mock_avd_spec, no_prompts=True)

        self.assertEqual(report.data.get("devices_failing_boot"),
                         self._EXPECTED_DEVICES_IN_FAILED_REPORT)
        self.assertEqual(report.errors, ["timeout"])

    # pylint: disable=protected-access
    @mock.patch("acloud.create.local_image_local_instance.os.path.isfile")
    def testFindCvdHostBinaries(self, mock_isfile):
        """Test FindCvdHostBinaries."""
        cvd_host_dir = "/unit/test"
        mock_isfile.return_value = None

        with mock.patch.dict("acloud.internal.lib.ota_tools.os.environ",
                             {"ANDROID_HOST_OUT": cvd_host_dir}, clear=True):
            with self.assertRaises(errors.GetCvdLocalHostPackageError):
                self.local_image_local_instance._FindCvdHostBinaries(
                    [cvd_host_dir])

        mock_isfile.side_effect = (
            lambda path: path == "/unit/test/bin/launch_cvd")

        with mock.patch.dict("acloud.internal.lib.ota_tools.os.environ",
                             {"ANDROID_HOST_OUT": cvd_host_dir}, clear=True):
            path = self.local_image_local_instance._FindCvdHostBinaries([])
            self.assertEqual(path, cvd_host_dir)

        with mock.patch.dict("acloud.internal.lib.ota_tools.os.environ",
                             dict(), clear=True):
            path = self.local_image_local_instance._FindCvdHostBinaries(
                [cvd_host_dir])
            self.assertEqual(path, cvd_host_dir)

    # pylint: disable=protected-access
    @mock.patch.object(instance, "GetLocalInstanceRuntimeDir")
    @mock.patch.object(utils, "CheckUserInGroups")
    def testPrepareLaunchCVDCmd(self, mock_usergroups, mock_cvd_dir):
        """test PrepareLaunchCVDCmd."""
        mock_usergroups.return_value = False
        mock_cvd_dir.return_value = "fake_cvd_dir"
        hw_property = {"cpu": "fake", "x_res": "fake", "y_res": "fake",
                       "dpi":"fake", "memory": "fake", "disk": "fake"}
        constants.LIST_CF_USER_GROUPS = ["group1", "group2"]

        launch_cmd = self.local_image_local_instance.PrepareLaunchCVDCmd(
            constants.CMD_LAUNCH_CVD, hw_property, True, "fake_image_dir",
            "fake_cvd_dir", False, None)
        self.assertEqual(launch_cmd, self.LAUNCH_CVD_CMD_WITH_DISK)

        # "disk" doesn't exist in hw_property.
        hw_property = {"cpu": "fake", "x_res": "fake", "y_res": "fake",
                       "dpi": "fake", "memory": "fake"}
        launch_cmd = self.local_image_local_instance.PrepareLaunchCVDCmd(
            constants.CMD_LAUNCH_CVD, hw_property, True, "fake_image_dir",
            "fake_cvd_dir", False, None)
        self.assertEqual(launch_cmd, self.LAUNCH_CVD_CMD_NO_DISK)

        # "gpu" is enabled with "default"
        launch_cmd = self.local_image_local_instance.PrepareLaunchCVDCmd(
            constants.CMD_LAUNCH_CVD, hw_property, True, "fake_image_dir",
            "fake_cvd_dir", False, "default")
        self.assertEqual(launch_cmd, self.LAUNCH_CVD_CMD_NO_DISK_WITH_GPU)

        launch_cmd = self.local_image_local_instance.PrepareLaunchCVDCmd(
            constants.CMD_LAUNCH_CVD, hw_property, True, "fake_image_dir",
            "fake_cvd_dir", True, None)
        self.assertEqual(launch_cmd, self.LAUNCH_CVD_CMD_WITH_WEBRTC)

    @mock.patch.object(utils, "GetUserAnswerYes")
    @mock.patch.object(list_instance, "GetActiveCVD")
    def testCheckRunningCvd(self, mock_cvd_running, mock_get_answer):
        """test _CheckRunningCvd."""
        local_instance_id = 3

        # Test that launch_cvd is running.
        mock_cvd_running.return_value = True
        mock_get_answer.return_value = False
        answer = self.local_image_local_instance._CheckRunningCvd(
            local_instance_id)
        self.assertFalse(answer)

        # Test that launch_cvd is not running.
        mock_cvd_running.return_value = False
        answer = self.local_image_local_instance._CheckRunningCvd(
            local_instance_id)
        self.assertTrue(answer)

    # pylint: disable=protected-access
    @mock.patch.dict("os.environ", clear=True)
    def testLaunchCVD(self):
        """test _LaunchCvd should call subprocess.Popen with the specific env"""
        local_instance_id = 3
        launch_cvd_cmd = "launch_cvd"
        host_bins_path = "host_bins_path"
        cvd_env = {}
        cvd_env[constants.ENV_CVD_HOME] = "fake_home"
        cvd_env[constants.ENV_CUTTLEFISH_INSTANCE] = str(local_instance_id)
        cvd_env[constants.ENV_ANDROID_HOST_OUT] = host_bins_path
        process = mock.MagicMock()
        process.wait.return_value = True
        process.returncode = 0
        self.Patch(subprocess, "Popen", return_value=process)
        self.Patch(instance, "GetLocalInstanceHomeDir",
                   return_value="fake_home")
        self.Patch(os, "makedirs")
        self.Patch(shutil, "rmtree")

        self.local_image_local_instance._LaunchCvd(launch_cvd_cmd,
                                                   local_instance_id,
                                                   host_bins_path)
        # pylint: disable=no-member
        subprocess.Popen.assert_called_once_with(launch_cvd_cmd,
                                                 shell=True,
                                                 stderr=subprocess.STDOUT,
                                                 env=cvd_env)


if __name__ == "__main__":
    unittest.main()
