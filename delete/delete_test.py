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
"""Tests for delete."""

import unittest

from acloud.delete import delete


# pylint: disable=invalid-name,protected-access
class DeleteTest(unittest.TestCase):
    """Test delete functions."""

    # pylint: disable=protected-access
    def testFilterInstancesByUser(self):
        """Test _FilterInstancesByUser."""
        user = "instance_match_user"
        matched_instance = "instance_1"
        instances = [
            {"name": matched_instance,
             "metadata": {"items": [{"key": "user",
                                     "value": user}]}},
            {"name": "instance_2",
             "metadata": {"items": [{"key": "user",
                                     "value": "instance_no_match_user"}]}}]
        expected_instances = [matched_instance]
        self.assertEqual(expected_instances,
                         delete._FilterInstancesByUser(instances, user))


if __name__ == "__main__":
    unittest.main()
