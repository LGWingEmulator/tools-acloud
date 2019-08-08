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
"""Tests for remote_instance_cf_device_factory."""

import glob
import os
import subprocess
import time
import unittest
import uuid

import mock

from acloud.create import avd_spec
from acloud.internal import constants
from acloud.internal.lib import auth
from acloud.internal.lib import cvd_compute_client
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils
from acloud.public.actions import remote_instance_cf_device_factory


class RemoteInstanceDeviceFactoryTest(driver_test_lib.BaseDriverTest):
    """Test RemoteInstanceDeviceFactory method."""

    def setUp(self):
        """Set up the test."""
        super(RemoteInstanceDeviceFactoryTest, self).setUp()
        self.Patch(auth, "CreateCredentials", return_value=mock.MagicMock())
        self.Patch(cvd_compute_client.CvdComputeClient, "InitResourceHandle")

    # pylint: disable=protected-access
    def testSSHExecuteWithRetry(self):
        """test SSHExecuteWithRetry method."""
        self.Patch(time, "sleep")
        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory
        self.Patch(subprocess, "check_call",
                   side_effect=subprocess.CalledProcessError(
                       None, "ssh command fail."))
        self.assertRaises(subprocess.CalledProcessError,
                          factory._ShellCmdWithRetry,
                          "fake cmd")
        self.assertEqual(subprocess.check_call.call_count, #pylint: disable=no-member
                         remote_instance_cf_device_factory._SSH_CMD_MAX_RETRY + 1)
        self.Patch(subprocess, "check_call", return_value=True)
        self.assertEqual(factory._ShellCmdWithRetry("fake cmd"), True)

    # pylint: disable=protected-access
    @mock.patch.dict(os.environ, {constants.ENV_BUILD_TARGET:'fake-target'})
    def testCreateGceInstanceName(self):
        """test create gce instance."""
        self.Patch(utils, "GetBuildEnvironmentVariable",
                   return_value="test_environ")
        self.Patch(glob, "glob", return_vale=["fake.img"])
        # Mock uuid
        args = mock.MagicMock()
        args.config_file = ""
        args.avd_type = constants.TYPE_CF
        args.flavor = "phone"
        args.local_image = None
        args.adb_port = None
        fake_avd_spec = avd_spec.AVDSpec(args)

        fake_uuid = mock.MagicMock(hex="1234")
        self.Patch(uuid, "uuid4", return_value=fake_uuid)
        self.Patch(cvd_compute_client.CvdComputeClient, "CreateInstance")
        fake_host_package_name = "/fake/host_package.tar.gz"
        fake_image_name = "/fake/aosp_cf_x86_phone-img-eng.username.zip"

        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-aosp-cf-x86-phone")

        # Can't get target name from zip file name.
        fake_image_name = "/fake/aosp_cf_x86_phone.username.zip"
        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-fake-target")

        # No image zip path, it uses local build images.
        fake_image_name = ""
        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-fake-target")


if __name__ == "__main__":
    unittest.main()
