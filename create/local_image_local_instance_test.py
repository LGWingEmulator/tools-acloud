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

import unittest
import mock

from acloud.create import local_image_local_instance
from acloud.list import instance
from acloud.internal import constants
from acloud.internal.lib import utils


class LocalImageLocalInstanceTest(unittest.TestCase):
    """Test LocalImageLocalInstance method."""

    LAUNCH_CVD_CMD_WITH_DISK = """sg group1 <<EOF
sg group2
launch_cvd -daemon -cpus fake -x_res fake -y_res fake -dpi fake -memory_mb fake -system_image_dir fake_image_dir -instance_dir fake_cvd_dir -blank_data_image_mb fake -data_policy always_create
EOF"""

    LAUNCH_CVD_CMD_NO_DISK = """sg group1 <<EOF
sg group2
launch_cvd -daemon -cpus fake -x_res fake -y_res fake -dpi fake -memory_mb fake -system_image_dir fake_image_dir -instance_dir fake_cvd_dir
EOF"""

    def setUp(self):
        """Initialize new LocalImageLocalInstance."""
        self.local_image_local_instance = local_image_local_instance.LocalImageLocalInstance()

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
            constants.CMD_LAUNCH_CVD, hw_property, "fake_image_dir",
            "fake_cvd_dir")
        self.assertEqual(launch_cmd, self.LAUNCH_CVD_CMD_WITH_DISK)

        # "disk" doesn't exist in hw_property.
        hw_property = {"cpu": "fake", "x_res": "fake", "y_res": "fake",
                       "dpi":"fake", "memory": "fake"}
        launch_cmd = self.local_image_local_instance.PrepareLaunchCVDCmd(
            constants.CMD_LAUNCH_CVD, hw_property, "fake_image_dir",
            "fake_cvd_dir")
        self.assertEqual(launch_cmd, self.LAUNCH_CVD_CMD_NO_DISK)

    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "_LaunchCvd")
    @mock.patch.object(utils, "GetUserAnswerYes")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "IsLocalCVDRunning")
    @mock.patch.object(local_image_local_instance.LocalImageLocalInstance,
                       "IsLocalImageOccupied")
    def testCheckLaunchCVD(self, mock_image_occupied, mock_cvd_running,
                           mock_get_answer,
                           mock_launch_cvd):
        """test CheckLaunchCVD."""
        launch_cvd_cmd = "fake_launch_cvd"
        host_bins_path = "fake_host_path"
        local_instance_id = 3
        local_image_path = "fake_image_path"

        # Test if image is in use.
        mock_cvd_running.return_value = False
        mock_image_occupied.return_value = True
        with self.assertRaises(SystemExit):
            self.local_image_local_instance.CheckLaunchCVD(launch_cvd_cmd,
                                                           host_bins_path,
                                                           local_instance_id,
                                                           local_image_path)
        # Test if launch_cvd is running.
        mock_image_occupied.return_value = False
        mock_cvd_running.return_value = True
        mock_get_answer.return_value = False
        with self.assertRaises(SystemExit):
            self.local_image_local_instance.CheckLaunchCVD(launch_cvd_cmd,
                                                           host_bins_path,
                                                           local_instance_id,
                                                           local_image_path)

        # Test if there's no using image and no conflict launch_cvd process.
        mock_image_occupied.return_value = False
        mock_cvd_running.return_value = False
        self.local_image_local_instance.CheckLaunchCVD(launch_cvd_cmd,
                                                       host_bins_path,
                                                       local_instance_id,
                                                       local_image_path)
        mock_launch_cvd.assert_called_once_with(
            "fake_launch_cvd", 3, timeout=local_image_local_instance._LAUNCH_CVD_TIMEOUT_SECS)

if __name__ == "__main__":
    unittest.main()
