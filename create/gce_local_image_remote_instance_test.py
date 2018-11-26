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
"""Tests for gce_local_image_remote_instance."""

import unittest
import os
import mock

from acloud import errors
from acloud.create.gce_local_image_remote_instance import GceLocalImageRemoteInstance
from acloud.internal.lib import driver_test_lib


# pylint: disable=invalid-name, protected-access
class GceLocalImageRemoteInstanceTest(driver_test_lib.BaseDriverTest):
    """Test gce_local_image_remote_instance methods."""

    def setUp(self):
        """Initialize gce_local_image_remote_instance."""
        super(GceLocalImageRemoteInstanceTest, self).setUp()
        self.build_client = mock.MagicMock()
        self.GceLocalImageRemoteInstance = GceLocalImageRemoteInstance()

    def testGetGceLocalImagePath(self):
        """Test get gce local image path."""
        self.Patch(os.path, "isfile", return_value=True)
        # Verify when specify --local-image ~/XXX.tar.gz.
        fake_image_path = "~/gce_local_image_dir/gce_image.tar.gz"
        self.Patch(os.path, "exists", return_value=True)
        self.assertEqual(
            self.GceLocalImageRemoteInstance._GetGceLocalImagePath(
                fake_image_path), "~/gce_local_image_dir/gce_image.tar.gz")

        # Verify when specify --local-image ~/XXX.img.
        fake_image_path = "~/gce_local_image_dir/gce_image.img"
        self.assertEqual(
            self.GceLocalImageRemoteInstance._GetGceLocalImagePath(
                fake_image_path), "~/gce_local_image_dir/gce_image.img")

        # Verify if exist argument --local-image as a directory.
        self.Patch(os.path, "isfile", return_value=False)
        self.Patch(os.path, "exists", return_value=True)
        fake_image_path = "~/gce_local_image_dir/"
        # Default to find */avd-system.tar.gz if exist then return the path.
        self.assertEqual(
            self.GceLocalImageRemoteInstance._GetGceLocalImagePath(
                fake_image_path), "~/gce_local_image_dir/avd-system.tar.gz")

        # Otherwise choose raw file */android_system_disk_syslinux.img if
        # exist then return the path.
        self.Patch(os.path, "exists", side_effect=[False, True])
        self.assertEqual(
            self.GceLocalImageRemoteInstance._GetGceLocalImagePath(
                fake_image_path), "~/gce_local_image_dir/android_system_disk_syslinux.img")

        # Both _GCE_LOCAL_IMAGE_CANDIDATE could not be found then raise error.
        self.Patch(os.path, "exists", side_effect=[False, False])
        self.assertRaises(errors.BootImgDoesNotExist,
                          self.GceLocalImageRemoteInstance._GetGceLocalImagePath,
                          fake_image_path)


if __name__ == "__main__":
    unittest.main()
