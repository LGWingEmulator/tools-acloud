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

import os
import unittest

import mock

from acloud import errors
from acloud.create import local_image_remote_instance
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils


class LocalImageRemoteInstanceTest(driver_test_lib.BaseDriverTest):
    """Test LocalImageRemoteInstance method."""

    def setUp(self):
        """Initialize new LocalImageRemoteInstance."""
        super(LocalImageRemoteInstanceTest, self).setUp()
        self.local_image_remote_instance = local_image_remote_instance.LocalImageRemoteInstance()

    def testVerifyHostPackageArtifactsExist(self):
        """test verify host package artifacts exist."""
        # Can't find the cvd host package
        with mock.patch("os.path.exists") as exists:
            exists.return_value = False
            self.assertRaises(
                errors.GetCvdLocalHostPackageError,
                self.local_image_remote_instance.VerifyHostPackageArtifactsExist)

        self.Patch(os.environ, "get", return_value="/fake_dir2")
        self.Patch(utils, "GetDistDir", return_value="/fake_dir1")
        # First path is host out dir, 2nd path is dist dir.
        self.Patch(os.path, "exists",
                   side_effect=[False, True])

        # Find cvd host in dist dir.
        self.assertEqual(
            self.local_image_remote_instance.VerifyHostPackageArtifactsExist(),
            "/fake_dir1/cvd-host_package.tar.gz")

        # Find cvd host in host out dir.
        self.Patch(os.environ, "get", return_value="/fake_dir2")
        self.Patch(utils, "GetDistDir", return_value=None)
        with mock.patch("os.path.exists") as exists:
            exists.return_value = True
            self.assertEqual(
                self.local_image_remote_instance.VerifyHostPackageArtifactsExist(),
                "/fake_dir2/cvd-host_package.tar.gz")


if __name__ == "__main__":
    unittest.main()
