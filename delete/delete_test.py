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
import subprocess
import mock

from acloud.delete import delete
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils


# pylint: disable=invalid-name,protected-access,unused-argument,no-member
class DeleteTest(driver_test_lib.BaseDriverTest):
    """Test delete functions."""

    # pylint: disable=protected-access
    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("subprocess.check_output")
    def testGetStopcvd(self, mock_subprocess, mock_path_exist):
        """Test _GetStopCvd."""
        mock_subprocess.side_effect = ["fake_id",
                                       "/tmp/bin/run_cvd"]
        expected_value = "/tmp/bin/stop_cvd"
        self.assertEqual(expected_value, delete._GetStopCvd())

    @mock.patch.object(delete, "_GetStopCvd", return_value="")
    @mock.patch("subprocess.check_call")
    def testDeleteLocalInstance(self, mock_subprocess, mock_get_stopcvd):
        """Test DeleteLocalInstance."""
        mock_subprocess.return_value = True
        instance_object = mock.MagicMock()
        instance_object.instance_dir = "fake_instance_dir"
        instance_object.name = "local-instance"
        delete_report = delete.DeleteLocalInstance(instance_object)
        self.assertEqual(delete_report.data, {
            "deleted": [
                {
                    "type": "instance",
                    "name": "local-instance",
                },
            ],
        })
        self.assertEqual(delete_report.command, "delete")
        self.assertEqual(delete_report.status, "SUCCESS")

    # pylint: disable=protected-access, no-member
    def testCleanupSSVncviwer(self):
        """test cleanup ssvnc viewer."""
        fake_vnc_port = 9999
        fake_ss_vncviewer_pattern = delete._SSVNC_VIEWER_PATTERN % {
            "vnc_port": fake_vnc_port}
        self.Patch(utils, "IsCommandRunning", return_value=True)
        self.Patch(subprocess, "check_call", return_value=True)
        delete.CleanupSSVncviewer(fake_vnc_port)
        subprocess.check_call.assert_called_with(["pkill", "-9", "-f", fake_ss_vncviewer_pattern])

        subprocess.check_call.call_count = 0
        self.Patch(utils, "IsCommandRunning", return_value=False)
        subprocess.check_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
