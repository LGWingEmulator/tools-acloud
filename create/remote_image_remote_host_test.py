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
"""Tests for remote_image_local_instance."""

import unittest
import os
import mock

from acloud.create import create_common
from acloud.create import remote_image_remote_host
from acloud.internal.lib import driver_test_lib


# pylint: disable=invalid-name, protected-access
class RemoteImageRemoteHostTest(driver_test_lib.BaseDriverTest):
    """Test remote_image_local_instance methods."""

    def setUp(self):
        """Initialize remote_image_local_instance."""
        super(RemoteImageRemoteHostTest, self).setUp()
        self._fake_remote_image = {"build_target" : "aosp_cf_x86_phone-userdebug",
                                   "build_id": "1234"}
        self._extract_path = "/tmp/1111/"

    @mock.patch.object(create_common, "DownloadRemoteArtifact")
    def testDownloadAndProcessArtifact(self, mock_download):
        """Test process remote cuttlefish image."""
        avd_spec = mock.MagicMock()
        avd_spec.cfg = mock.MagicMock()
        avd_spec.remote_image = self._fake_remote_image
        avd_spec.image_download_dir = "/tmp"
        self.Patch(os.path, "exists", return_value=False)
        self.Patch(os, "makedirs")
        remote_image_remote_host.DownloadAndProcessArtifact(
            avd_spec, self._extract_path)
        build_id = "1234"
        build_target = "aosp_cf_x86_phone-userdebug"
        checkfile1 = "aosp_cf_x86_phone-img-1234.zip"
        checkfile2 = "cvd-host_package.tar.gz"

        # To validate DownloadArtifact runs twice.
        self.assertEqual(mock_download.call_count, 2)

        # To validate DownloadArtifact arguments correct.
        mock_download.assert_has_calls([
            mock.call(avd_spec.cfg, build_target, build_id, checkfile1,
                      self._extract_path, decompress=True),
            mock.call(avd_spec.cfg, build_target, build_id, checkfile2,
                      self._extract_path)], any_order=True)


if __name__ == "__main__":
    unittest.main()
