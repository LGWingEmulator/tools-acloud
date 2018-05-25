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
"""Tests for acloud.public.actions.create_goldfish_actions."""
import uuid

import unittest
import mock
from acloud.internal.lib import android_build_client
from acloud.internal.lib import android_compute_client
from acloud.internal.lib import auth
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import goldfish_compute_client
from acloud.public.actions import create_goldfish_action


class CreateGoldfishActionTest(driver_test_lib.BaseDriverTest):
    """Tests create_goldfish_action."""

    IP = "127.0.0.1"
    INSTANCE = "fake-instance"
    IMAGE = "fake-image"
    BUILD_TARGET = "fake-build-target"
    EMULATOR_TARGET = "emu-fake-target"
    BUILD_ID = "12345"
    EMULATOR_BUILD_ID = "1234567"
    GPU = "nvidia-tesla-k80"
    BRANCH = "fake-branch"
    EMULATOR_BRANCH = "emu-fake-branch"
    GOLDFISH_HOST_IMAGE_NAME = "fake-stable-host-image-name"
    GOLDFISH_HOST_IMAGE_PROJECT = "fake-stable-host-image-project"
    EXTRA_DATA_DISK_GB = 4

    def setUp(self):
        """Sets up the test."""
        super(CreateGoldfishActionTest, self).setUp()
        self.build_client = mock.MagicMock()
        self.Patch(
            android_build_client,
            "AndroidBuildClient",
            return_value=self.build_client)
        self.compute_client = mock.MagicMock()
        self.Patch(
            goldfish_compute_client,
            "GoldfishComputeClient",
            return_value=self.compute_client)
        self.Patch(
            android_compute_client,
            "AndroidComputeClient",
            return_value=self.compute_client)
        self.Patch(auth, "CreateCredentials", return_value=mock.MagicMock())

    def _CreateCfg(self):
        """A helper method that creates a mock configuration object."""
        cfg = mock.MagicMock()
        cfg.service_account_name = "fake@service.com"
        cfg.service_account_private_key_path = "/fake/path/to/key"
        cfg.zone = "fake_zone"
        cfg.ssh_private_key_path = ""
        cfg.ssh_public_key_path = ""
        cfg.stable_goldfish_host_image_name = self.GOLDFISH_HOST_IMAGE_NAME
        cfg.stable_goldfish_host_image_project = self.GOLDFISH_HOST_IMAGE_PROJECT
        cfg.emulator_build_target = self.EMULATOR_TARGET
        cfg.extra_data_disk_size_gb = self.EXTRA_DATA_DISK_GB
        return cfg

    def testCreateDevices(self):
        """Tests CreateDevices."""
        cfg = self._CreateCfg()

        # Mock uuid
        fake_uuid = mock.MagicMock(hex="1234")
        self.Patch(uuid, "uuid4", return_value=fake_uuid)

        # Mock compute client methods
        self.compute_client.GetInstanceIP.return_value = self.IP
        self.compute_client.GenerateImageName.return_value = self.IMAGE
        self.compute_client.GenerateInstanceName.return_value = self.INSTANCE

        # Mock build client method
        self.build_client.GetBranch.side_effect = [
            self.BRANCH, self.EMULATOR_BRANCH
        ]

        # Call CreateDevices
        report = create_goldfish_action.CreateDevices(
            cfg, self.BUILD_TARGET, self.BUILD_ID, self.EMULATOR_BUILD_ID,
            self.GPU)

        # Verify
        self.compute_client.CreateInstance.assert_called_with(
            instance=self.INSTANCE,
            blank_data_disk_size_gb=self.EXTRA_DATA_DISK_GB,
            image_name=self.GOLDFISH_HOST_IMAGE_NAME,
            image_project=self.GOLDFISH_HOST_IMAGE_PROJECT,
            build_target=self.BUILD_TARGET,
            branch=self.BRANCH,
            build_id=self.BUILD_ID,
            emulator_branch=self.EMULATOR_BRANCH,
            emulator_build_id=self.EMULATOR_BUILD_ID,
            gpu=self.GPU)

        self.assertEquals(report.data, {
            "devices": [
                {
                    "instance_name": self.INSTANCE,
                    "ip": self.IP,
                },
            ],
        })
        self.assertEquals(report.command, "create_gf")
        self.assertEquals(report.status, "SUCCESS")

if __name__ == "__main__":
    unittest.main()
