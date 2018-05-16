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

"""Tests for acloud.public.actions.common_operations."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import mock

import unittest
from acloud.internal.lib import android_build_client
from acloud.internal.lib import android_compute_client
from acloud.internal.lib import auth
from acloud.internal.lib import driver_test_lib
from acloud.public import report
from acloud.public.actions import common_operations


class CommonOperationsTest(driver_test_lib.BaseDriverTest):

  IP = "127.0.0.1"
  INSTANCE = "fake-instance"
  CMD = "test-cmd"

  def setUp(self):
    """Set up the test."""
    super(CommonOperationsTest, self).setUp()
    self.build_client = mock.MagicMock()
    self.device_factory = mock.MagicMock()
    self.Patch(
        android_build_client,
        "AndroidBuildClient",
        return_value=self.build_client)
    self.compute_client = mock.MagicMock()
    self.Patch(
        android_compute_client,
        "AndroidComputeClient",
        return_value=self.compute_client)
    self.Patch(auth, "CreateCredentials", return_value=mock.MagicMock())
    self.Patch(self.compute_client, "GetInstanceIP", return_value=self.IP)
    self.Patch(
        self.device_factory, "CreateInstance", return_value=self.INSTANCE)
    self.Patch(self.device_factory, "GetComputeClient",
               return_value=self.compute_client)

  def _CreateCfg(self):
    """A helper method that creates a mock configuration object."""
    cfg = mock.MagicMock()
    cfg.service_account_name = "fake@service.com"
    cfg.service_account_private_key_path = "/fake/path/to/key"
    cfg.zone = "fake_zone"
    cfg.disk_image_name = "fake_image.tar.gz"
    cfg.disk_image_mime_type = "fake/type"
    cfg.ssh_private_key_path = ""
    cfg.ssh_public_key_path = ""
    return cfg

  def testDevicePoolCreateDevices(self):
    pool = common_operations.DevicePool(self.device_factory)
    pool.CreateDevices(5)
    self.assertEqual(self.device_factory.CreateInstance.call_count, 5)
    self.assertEqual(len(pool.devices), 5)

  def testCreateDevices(self):
    cfg = self._CreateCfg()
    r = common_operations.CreateDevices(self.CMD, cfg, self.device_factory, 1)
    self.assertEqual(r.command, self.CMD)
    self.assertEqual(r.status, report.Status.SUCCESS)
    self.assertEqual(
        r.data, {"devices": [{
            "ip": self.IP,
            "instance_name": self.INSTANCE
        }]})


if __name__ == "__main__":
  unittest.main()
