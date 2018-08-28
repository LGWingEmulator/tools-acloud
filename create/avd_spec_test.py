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

from acloud.create import avd_spec
from acloud.internal import constants


# pylint: disable=invalid-name,protected-access
class AvdSpecTest(unittest.TestCase):
    """Test GCP Setup steps."""

    def setUp(self):
        """Initialize new avd_spec.AVDSpec."""
        self.args = mock.MagicMock()
        self.args.local_image = ""
        self.AvdSpec = avd_spec.AVDSpec(self.args)

    def testProcessLocalImageArgs(self):
        """Test process args.local_image."""
        # Specified local_image with an arg
        self.args.local_image = "test_path"
        self.AvdSpec._ProcessLocalImageArgs(self.args)
        self.assertEqual(self.AvdSpec._local_image_path, "test_path")

        # Specified local_image with no arg
        self.args.local_image = None
        with mock.patch.dict("os.environ", {"ANDROID_PRODUCT_OUT": "test_environ"}):
            self.AvdSpec._ProcessLocalImageArgs(self.args)
            self.assertEqual(self.AvdSpec._local_image_path, "test_environ")

    def testProcessImageArgs(self):
        """Test process image source."""
        # No specified local_image, image source is from remote
        self.args.local_image = ""
        self.AvdSpec._ProcessImageArgs(self.args)
        self.assertEqual(self.AvdSpec._image_source, constants.IMAGE_SRC_REMOTE)
        self.assertEqual(self.AvdSpec._local_image_path, None)

        # Specified local_image with an arg, image source is from local
        self.args.local_image = "test_path"
        self.AvdSpec._ProcessImageArgs(self.args)
        self.assertEqual(self.AvdSpec._image_source, constants.IMAGE_SRC_LOCAL)
        self.assertEqual(self.AvdSpec._local_image_path, "test_path")


if __name__ == "__main__":
    unittest.main()
