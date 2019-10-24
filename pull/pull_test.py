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
"""Tests for pull."""
import unittest

import mock

from acloud import errors
from acloud.pull import pull
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils


class PullTest(driver_test_lib.BaseDriverTest):
    """Test pull."""

    def testSelectLogFileToPull(self):
        """test choose log files from the remote instance."""
        ssh = mock.MagicMock()

        # Test only one log file case
        log_files = ["file1.log"]
        self.Patch(pull, "GetAllLogFilePaths", return_value=log_files)
        expected_result = ["file1.log"]
        self.assertEqual(pull.SelectLogFileToPull(ssh), expected_result)

        # Test no log files case
        self.Patch(pull, "GetAllLogFilePaths", return_value=[])
        with self.assertRaises(errors.CheckPathError):
            pull.SelectLogFileToPull(ssh)

        # Test two log files case.
        log_files = ["file1.log", "file2.log"]
        choose_log = ["file2.log"]
        self.Patch(pull, "GetAllLogFilePaths", return_value=log_files)
        self.Patch(utils, "GetAnswerFromList", return_value=choose_log)
        expected_result = ["file2.log"]
        self.assertEqual(pull.SelectLogFileToPull(ssh), expected_result)

        # Test user provided file name exist.
        log_files = ["/home/vsoc-01/cuttlefish_runtime/file1.log",
                     "/home/vsoc-01/cuttlefish_runtime/file2.log"]
        input_file = "file1.log"
        self.Patch(pull, "GetAllLogFilePaths", return_value=log_files)
        expected_result = ["/home/vsoc-01/cuttlefish_runtime/file1.log"]
        self.assertEqual(pull.SelectLogFileToPull(ssh, input_file), expected_result)

        # Test user provided file name not exist.
        log_files = ["/home/vsoc-01/cuttlefish_runtime/file1.log",
                     "/home/vsoc-01/cuttlefish_runtime/file2.log"]
        input_file = "not_exist.log"
        self.Patch(pull, "GetAllLogFilePaths", return_value=log_files)
        with self.assertRaises(errors.CheckPathError):
            pull.SelectLogFileToPull(ssh, input_file)

    def testFilterLogfiles(self):
        """test filer log file from black list."""
        # Filter out file name is "kernel".
        files = ["kernel.log", "logcat", "kernel"]
        expected_result = ["kernel.log", "logcat"]
        self.assertEqual(pull.FilterLogfiles(files), expected_result)

        # Filter out file extension is ".img".
        files = ["kernel.log", "system.img", "userdata.img", "launcher.log"]
        expected_result = ["kernel.log", "launcher.log"]
        self.assertEqual(pull.FilterLogfiles(files), expected_result)


if __name__ == '__main__':
    unittest.main()
