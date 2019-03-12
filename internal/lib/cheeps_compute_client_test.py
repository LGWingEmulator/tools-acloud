#!/usr/bin/env python
#
# Copyright 2019 - The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for acloud.internal.lib.cheeps_compute_client."""

import unittest
import mock

from acloud.internal.lib import cheeps_compute_client
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import gcompute_client


class CheepsComputeClientTest(driver_test_lib.BaseDriverTest):
    """Test CheepsComputeClient."""

    SSH_PUBLIC_KEY_PATH = ""
    INSTANCE = "fake-instance"
    IMAGE = "fake-image"
    IMAGE_PROJECT = "fake-image-project"
    MACHINE_TYPE = "fake-machine-type"
    NETWORK = "fake-network"
    ZONE = "fake-zone"
    METADATA = {"metadata_key": "metadata_value"}
    BOOT_DISK_SIZE_GB = 10
    ANDROID_BUILD_ID = 123

    def _GetFakeConfig(self):
        """Create a fake configuration object.

        Returns:
            A fake configuration mock object.
        """

        fake_cfg = mock.MagicMock()
        fake_cfg.ssh_public_key_path = self.SSH_PUBLIC_KEY_PATH
        fake_cfg.machine_type = self.MACHINE_TYPE
        fake_cfg.network = self.NETWORK
        fake_cfg.zone = self.ZONE
        fake_cfg.metadata_variable = self.METADATA
        return fake_cfg

    def setUp(self):
        """Set up the test."""

        super(CheepsComputeClientTest, self).setUp()
        self.Patch(cheeps_compute_client.CheepsComputeClient,
                   "InitResourceHandle")
        self.cheeps_compute_client = (
            cheeps_compute_client.CheepsComputeClient(self._GetFakeConfig(),
                                                      mock.MagicMock()))
        self.Patch(
            gcompute_client.ComputeClient, "CompareMachineSize", return_value=1)
        self.Patch(
            gcompute_client.ComputeClient,
            "GetImage",
            return_value={"diskSizeGb": self.BOOT_DISK_SIZE_GB})
        self.Patch(gcompute_client.ComputeClient, "CreateInstance")

    def testCreateInstance(self):
        """Test CreateInstance."""

        expected_metadata = {'android_build_id': self.ANDROID_BUILD_ID}
        expected_metadata.update(self.METADATA)

        self.cheeps_compute_client.CreateInstance(
            self.INSTANCE, self.IMAGE, self.IMAGE_PROJECT, self.ANDROID_BUILD_ID)
        # pylint: disable=no-member
        gcompute_client.ComputeClient.CreateInstance.assert_called_with(
            self.cheeps_compute_client,
            instance=self.INSTANCE,
            image_name=self.IMAGE,
            image_project=self.IMAGE_PROJECT,
            disk_args=None,
            metadata=expected_metadata,
            machine_type=self.MACHINE_TYPE,
            network=self.NETWORK,
            zone=self.ZONE)

if __name__ == "__main__":
    unittest.main()
