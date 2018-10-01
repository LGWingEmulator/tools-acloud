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

import unittest
import mock

from acloud import errors
from acloud.create import local_image_remote_instance


class LocalImageRemoteInstanceTest(unittest.TestCase):
    """Test LocalImageRemoteInstance method."""

    def setUp(self):
        """Initialize new LocalImageRemoteInstance."""
        self.local_image_remote_instance = local_image_remote_instance.LocalImageRemoteInstance()

    def testVerifyHostPackageArtifactsExist(self):
        """test verify host package artifacts exist."""
        #can't find the cvd host package
        with mock.patch("os.path.exists") as exists:
            exists.return_value = False
            self.assertRaises(
                errors.GetCvdLocalHostPackageError, self.
                local_image_remote_instance.VerifyHostPackageArtifactsExist,
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


if __name__ == "__main__":
    unittest.main()
