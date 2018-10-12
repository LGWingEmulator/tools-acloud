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

import subprocess
import time
import unittest

import mock

from acloud import errors
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

    @mock.patch("glob.glob")
    def testVerifyArtifactsExist(self, mock_glob):
        """test verify artifacts exist."""
        mock_glob.return_value = ["/fake_dirs/image1.zip"]
        with mock.patch("os.path.exists") as exists:
            exists.return_value = True
            self.local_image_remote_instance.VerifyArtifactsExist("/fake_dirs")
            self.assertEqual(
                self.local_image_remote_instance.local_image_artifact,
                "/fake_dirs/image1.zip")
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


if __name__ == "__main__":
    unittest.main()
