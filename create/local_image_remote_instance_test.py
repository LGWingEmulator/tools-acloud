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
import uuid

import subprocess
import time
import unittest

import mock

from acloud import errors
from acloud.create import avd_spec
from acloud.create import create_common
from acloud.create import local_image_remote_instance
from acloud.internal.lib import auth
from acloud.internal.lib import cvd_compute_client
from acloud.internal.lib import driver_test_lib


class LocalImageRemoteInstanceTest(unittest.TestCase):
    """Test LocalImageRemoteInstance method."""

    def setUp(self):
        """Initialize new LocalImageRemoteInstance."""
        self.local_image_remote_instance = local_image_remote_instance.LocalImageRemoteInstance()

    def testVerifyHostPackageArtifactsExist(self):
        """test verify host package artifacts exist."""
        # Can't find the cvd host package
        with mock.patch("os.path.exists") as exists:
            exists.return_value = False
            self.assertRaises(
                errors.GetCvdLocalHostPackageError,
                self.local_image_remote_instance.VerifyHostPackageArtifactsExist,
                "/fake_dirs")

    def testVerifyArtifactsExist(self):
        """test verify artifacts exist."""
        with mock.patch("os.path.exists") as exists:
            exists.return_value = True
            self.local_image_remote_instance.VerifyArtifactsExist("/fake_dirs")
            self.assertEqual(
                self.local_image_remote_instance.cvd_host_package_artifact,
                "/fake_dirs/cvd-host_package.tar.gz")


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
        factory = local_image_remote_instance.RemoteInstanceDeviceFactory
        self.Patch(subprocess, "check_call",
                   side_effect=subprocess.CalledProcessError(
                       None, "ssh command fail."))
        self.assertRaises(subprocess.CalledProcessError,
                          factory._ShellCmdWithRetry,
                          "fake cmd")
        self.assertEqual(subprocess.check_call.call_count, #pylint: disable=no-member
                         local_image_remote_instance._SSH_CMD_MAX_RETRY + 1)
        self.Patch(subprocess, "check_call", return_value=True)
        self.assertEqual(factory._ShellCmdWithRetry("fake cmd"), True)

    # pylint: disable=protected-access
    @mock.patch.object(create_common, "VerifyLocalImageArtifactsExist")
    def testCreateGceInstanceName(self, mock_image):
        """test create gce instance."""
        # Mock uuid
        args = mock.MagicMock()
        args.local_image = "/tmp/path"
        args.config_file = ""
        args.avd_type = "cf"
        args.flavor = "phone"
        mock_image.return_value = "/fake/aosp_cf_x86_phone-img-eng.username.zip"
        fake_avd_spec = avd_spec.AVDSpec(args)

        fake_uuid = mock.MagicMock(hex="1234")
        self.Patch(uuid, "uuid4", return_value=fake_uuid)
        self.Patch(cvd_compute_client.CvdComputeClient, "CreateInstance")
        fake_host_package_name = "/fake/host_package.tar.gz"
        fake_image_name = "/fake/aosp_cf_x86_phone-img-eng.username.zip"

        factory = local_image_remote_instance.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-aosp-cf-x86-phone")

        fake_image_name = "/fake/aosp_cf_x86_phone.username.zip"
        factory = local_image_remote_instance.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-phone")

if __name__ == "__main__":
    unittest.main()
