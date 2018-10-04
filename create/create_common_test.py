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
"""Tests for create_common."""

import unittest
import mock

from acloud import errors
from acloud.create import create_common


# pylint: disable=invalid-name,protected-access
class CreateCommonTest(unittest.TestCase):
    """Test create_common functions."""

    # pylint: disable=protected-access
    def testProcessHWPropertyWithInvalidArgs(self):
        """Test ParseHWPropertyArgs with invalid args."""
        # Checking wrong property value.
        args_str = "cpu:3,disk:"
        with self.assertRaises(errors.MalformedDictStringError):
            create_common.ParseHWPropertyArgs(args_str)

        # Checking wrong property format.
        args_str = "cpu:3,disk"
        with self.assertRaises(errors.MalformedDictStringError):
            create_common.ParseHWPropertyArgs(args_str)

    def testParseHWPropertyStr(self):
        """Test ParseHWPropertyArgs."""
        expected_dict = {"cpu": "2", "resolution": "1080x1920", "dpi": "240",
                         "memory": "4g", "disk": "4g"}
        args_str = "cpu:2,resolution:1080x1920,dpi:240,memory:4g,disk:4g"
        result_dict = create_common.ParseHWPropertyArgs(args_str)
        self.assertTrue(expected_dict == result_dict)

    @mock.patch("glob.glob")
    def testVerifyLocalImageArtifactsExist(self, mock_glob):
        """Test VerifyArtifactsPath."""
        #can't find the image
        mock_glob.return_value = []
        self.assertRaises(errors.GetLocalImageError,
                          create_common.VerifyLocalImageArtifactsExist,
                          "/fake_dirs")

        mock_glob.return_value = [
            "/fake_dirs/aosp_cf_x86_phone-img-5046769.zip"
        ]
        self.assertEqual(
            create_common.VerifyLocalImageArtifactsExist("/fake_dirs"),
            "/fake_dirs/aosp_cf_x86_phone-img-5046769.zip")

    @mock.patch("__builtin__.raw_input")
    def testGetAnswerFromList(self, mock_raw_input):
        """Test GetAnswerFromList."""
        answer_list = ["image1.zip", "image2.zip", "image3.zip"]
        mock_raw_input.return_value = 0
        with self.assertRaises(SystemExit):
            create_common.GetAnswerFromList(answer_list)
        mock_raw_input.side_effect = [1, 2, 3]
        self.assertEqual(create_common.GetAnswerFromList(answer_list),
                         "image1.zip")
        self.assertEqual(create_common.GetAnswerFromList(answer_list),
                         "image2.zip")
        self.assertEqual(create_common.GetAnswerFromList(answer_list),
                         "image3.zip")

if __name__ == "__main__":
    unittest.main()
