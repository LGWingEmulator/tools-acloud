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
"""Tests for avd_spec."""

import unittest
import mock

from acloud import errors
from acloud.create import avd_spec
from acloud.create import create_common
from acloud.internal import constants


# pylint: disable=invalid-name,protected-access
class AvdSpecTest(unittest.TestCase):
    """Test avd_spec methods."""

    def setUp(self):
        """Initialize new avd_spec.AVDSpec."""
        self.args = mock.MagicMock()
        self.args.local_image = ""
        self.args.config_file = ""
        self.AvdSpec = avd_spec.AVDSpec(self.args)

    # pylint: disable=protected-access
    @mock.patch.object(create_common, "VerifyLocalImageArtifactsExist")
    def testProcessLocalImageArgs(self, mock_image):
        """Test process args.local_image."""
        # Specified local_image with an arg
        mock_image.return_value = "cf_x86_phone-img-eng.user.zip"
        self.args.local_image = "test_path"
        self.AvdSpec._ProcessLocalImageArgs(self.args)
        self.assertEqual(self.AvdSpec._local_image_dir, "test_path")

        # Specified local_image with no arg
        self.args.local_image = None
        with mock.patch.dict("os.environ", {"ANDROID_PRODUCT_OUT": "test_environ"}):
            self.AvdSpec._ProcessLocalImageArgs(self.args)
            self.assertEqual(self.AvdSpec._local_image_dir, "test_environ")

    @mock.patch.object(create_common, "VerifyLocalImageArtifactsExist")
    def testProcessImageArgs(self, mock_image):
        """Test process image source."""
        # No specified local_image, image source is from remote
        self.args.local_image = ""
        self.AvdSpec._ProcessImageArgs(self.args)
        self.assertEqual(self.AvdSpec._image_source, constants.IMAGE_SRC_REMOTE)
        self.assertEqual(self.AvdSpec._local_image_dir, None)

        # Specified local_image with an arg, image source is from local
        mock_image.return_value = "cf_x86_phone-img-eng.user.zip"
        self.args.local_image = "test_path"
        self.AvdSpec._ProcessImageArgs(self.args)
        self.assertEqual(self.AvdSpec._image_source, constants.IMAGE_SRC_LOCAL)
        self.assertEqual(self.AvdSpec._local_image_dir, "test_path")

    @mock.patch.object(avd_spec.AVDSpec, "_GetGitRemote")
    @mock.patch("subprocess.check_output")
    def testGetBranchFromRepo(self, mock_repo, mock_gitremote):
        """Test get branch name from repo info."""
        # Check aosp repo gets proper branch prefix.
        mock_gitremote.return_value = "aosp"
        mock_repo.return_value = "Manifest branch: master"
        self.assertEqual(self.AvdSpec._GetBranchFromRepo(), "aosp-master")

        # Check default repo gets default branch prefix.
        mock_gitremote.return_value = ""
        mock_repo.return_value = "Manifest branch: master"
        self.assertEqual(self.AvdSpec._GetBranchFromRepo(), "git_master")

        mock_repo.return_value = "Manifest branch:"
        with self.assertRaises(errors.GetBranchFromRepoInfoError):
            self.AvdSpec._GetBranchFromRepo()

    # pylint: disable=protected-access
    def testGetBuildTarget(self):
        """Test get build target name."""
        self.AvdSpec._remote_image[avd_spec._BUILD_BRANCH] = "aosp-master"
        self.AvdSpec._flavor = constants.FLAVOR_IOT
        self.args.avd_type = constants.TYPE_GCE
        self.assertEqual(
            self.AvdSpec._GetBuildTarget(self.args),
            "aosp_gce_x86_iot-userdebug")

        self.AvdSpec._remote_image[avd_spec._BUILD_BRANCH] = "aosp-master"
        self.AvdSpec._flavor = constants.FLAVOR_PHONE
        self.args.avd_type = constants.TYPE_CF
        self.assertEqual(
            self.AvdSpec._GetBuildTarget(self.args),
            "aosp_cf_x86_phone-userdebug")

        self.AvdSpec._remote_image[avd_spec._BUILD_BRANCH] = "git_branch"
        self.AvdSpec._flavor = constants.FLAVOR_PHONE
        self.args.avd_type = constants.TYPE_CF
        self.assertEqual(
            self.AvdSpec._GetBuildTarget(self.args),
            "cf_x86_phone-userdebug")

    # pylint: disable=protected-access
    def testProcessHWPropertyWithInvalidArgs(self):
        """Test _ProcessHWPropertyArgs with invalid args."""
        # Checking wrong resolution.
        args = mock.MagicMock()
        args.hw_property = "cpu:3,resolution:1280"
        with self.assertRaises(errors.InvalidHWPropertyError):
            self.AvdSpec._ProcessHWPropertyArgs(args)

        # Checking property should be int.
        args = mock.MagicMock()
        args.hw_property = "cpu:3,dpi:fake"
        with self.assertRaises(errors.InvalidHWPropertyError):
            self.AvdSpec._ProcessHWPropertyArgs(args)

        # Checking disk property should be with 'g' suffix.
        args = mock.MagicMock()
        args.hw_property = "cpu:3,disk:2"
        with self.assertRaises(errors.InvalidHWPropertyError):
            self.AvdSpec._ProcessHWPropertyArgs(args)

        # Checking memory property should be with 'g' suffix.
        args = mock.MagicMock()
        args.hw_property = "cpu:3,memory:2"
        with self.assertRaises(errors.InvalidHWPropertyError):
            self.AvdSpec._ProcessHWPropertyArgs(args)

    # pylint: disable=protected-access
    def testParseHWPropertyStr(self):
        """Test _ParseHWPropertyStr."""
        expected_dict = {"cpu": "2", "x_res": "1080", "y_res": "1920",
                         "dpi": "240", "memory": "4096", "disk": "4096"}
        args_str = "cpu:2,resolution:1080x1920,dpi:240,memory:4g,disk:4g"
        result_dict = self.AvdSpec._ParseHWPropertyStr(args_str)
        self.assertTrue(expected_dict == result_dict)

    def testGetFlavorFromLocalImage(self):
        """Test _GetFlavorFromLocalImage."""
        img_path = "/fack_path/cf_x86_tv-img-eng.user.zip"
        self.assertEqual(self.AvdSpec._GetFlavorFromLocalImage(img_path), "tv")

        # Flavor is not supported.
        img_path = "/fack_path/cf_x86_error-img-eng.user.zip"
        self.assertEqual(self.AvdSpec._GetFlavorFromLocalImage(img_path), None)


if __name__ == "__main__":
    unittest.main()
