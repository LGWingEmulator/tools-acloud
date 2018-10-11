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
import subprocess
import mock

from acloud import errors
from acloud.create.remote_image_local_instance import RemoteImageLocalInstance
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils
from acloud.setup import setup_common


# pylint: disable=invalid-name, protected-access
class RemoteImageLocalInstanceTest(driver_test_lib.BaseDriverTest):
    """Test remote_image_local_instance methods."""

    def setUp(self):
        """Initialize remote_image_local_instance."""
        super(RemoteImageLocalInstanceTest, self).setUp()
        self.build_client = mock.MagicMock()
        self.Patch(
            android_build_client,
            "AndroidBuildClient",
            return_value=self.build_client)
        self.Patch(auth, "CreateCredentials", return_value=mock.MagicMock())
        self.RemoteImageLocalInstance = RemoteImageLocalInstance()
        self._fake_remote_image = {"build_target" : "aosp_cf_x86_phone-userdebug",
                                   "build_id": "1234"}
        self._extract_path = "/tmp/acloud_image_artifacts/cuttlefish/1234"

    @mock.patch.object(RemoteImageLocalInstance, "_DownloadAndProcessImageFiles")
    def testGetImageArtifactsPath(self, mock_proc):
        """Test get image artifacts path."""
        avd_spec = mock.MagicMock()
        # raise errors.NoCuttlefishCommonInstalled
        self.Patch(setup_common, "PackageInstalled", return_value=False)
        self.assertRaises(errors.NoCuttlefishCommonInstalled,
                          self.RemoteImageLocalInstance.GetImageArtifactsPath,
                          avd_spec)

        # Valid _DownloadAndProcessImageFiles run.
        self.Patch(setup_common, "PackageInstalled", return_value=True)
        self.RemoteImageLocalInstance.GetImageArtifactsPath(avd_spec)
        mock_proc.assert_called_once_with(avd_spec)

    @mock.patch.object(RemoteImageLocalInstance, "_AclCfImageFiles")
    @mock.patch.object(RemoteImageLocalInstance, "_UnpackBootImage")
    @mock.patch.object(RemoteImageLocalInstance, "_DownloadRemoteImage")
    def testDownloadAndProcessImageFiles(self, mock_download, mock_unpack, mock_acl):
        """Test process remote cuttlefish image."""
        avd_spec = mock.MagicMock()
        avd_spec.cfg = mock.MagicMock()
        avd_spec.remote_image = self._fake_remote_image
        self.Patch(os.path, "exists", return_value=False)
        self.RemoteImageLocalInstance._DownloadAndProcessImageFiles(avd_spec)

        # To make sure each function execute once.
        mock_download.assert_called_once_with(
            avd_spec.cfg,
            avd_spec.remote_image["build_target"],
            avd_spec.remote_image["build_id"],
            self._extract_path)
        mock_unpack.assert_called_once_with(self._extract_path)
        mock_acl.assert_called_once_with(self._extract_path)
        # Clean extarcted folder after test completed.
        os.rmdir(self._extract_path)

    @mock.patch.object(utils, "TempDir")
    @mock.patch.object(utils, "Decompress")
    def testDownloadRemoteImage(self, mock_decompress, mock_tmpdir):
        """Test Download cuttlefish package."""
        avd_spec = mock.MagicMock()
        avd_spec.cfg = mock.MagicMock()
        avd_spec.remote_image = self._fake_remote_image
        mock_tmpdir.return_value = mock_tmpdir
        mock_tmpdir.__exit__ = mock.MagicMock(return_value=None)
        mock_tmpdir.__enter__ = mock.MagicMock(return_value="tmp")
        build_id = "1234"
        build_target = "aosp_cf_x86_phone-userdebug"
        checkfile1 = "aosp_cf_x86_phone-img-1234.zip"
        checkfile2 = "cvd-host_package.tar.gz"

        self.RemoteImageLocalInstance._DownloadRemoteImage(
            avd_spec.cfg,
            avd_spec.remote_image["build_target"],
            avd_spec.remote_image["build_id"],
            self._extract_path)

        # To validate DownloadArtifact runs twice.
        self.assertEqual(self.build_client.DownloadArtifact.call_count, 2)
        # To validate DownloadArtifact arguments correct.
        self.build_client.DownloadArtifact.assert_has_calls([
            mock.call(build_target, build_id, checkfile1,
                      "tmp/%s" % checkfile1),
            mock.call(build_target, build_id, checkfile2,
                      "tmp/%s" % checkfile2)], any_order=True)
        # To validate Decompress runs twice.
        self.assertEqual(mock_decompress.call_count, 2)

    @mock.patch.object(subprocess, "check_call")
    def testUnpackBootImage(self, mock_call):
        """Test Unpack boot image."""
        self.Patch(os.path, "exists", side_effect=[True, False])
        self.RemoteImageLocalInstance._UnpackBootImage(self._extract_path)
        # check_call run once when boot.img exist.
        self.assertEqual(mock_call.call_count, 1)
        # raise errors.BootImgDoesNotExist when boot.img doesn't exist.
        self.assertRaises(errors.BootImgDoesNotExist,
                          self.RemoteImageLocalInstance._UnpackBootImage,
                          self._extract_path)

    @mock.patch.object(subprocess, "check_call")
    def testAclCfImageFiles(self, mock_call):
        """Test acl related files."""
        self.Patch(os.path, "exists",
                   side_effect=[True, True, True, True, False, True, True])
        # Raise error when acl required file does not exist at 5th run cehck_call.
        self.assertRaises(errors.CheckPathError,
                          self.RemoteImageLocalInstance._AclCfImageFiles,
                          self._extract_path)
        # it should be run check_call 4 times before raise error.
        self.assertEqual(mock_call.call_count, 4)

if __name__ == "__main__":
    unittest.main()
