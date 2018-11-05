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
import mock

from acloud.delete import delete
from acloud.internal.lib import utils
from acloud.public import device_driver


# pylint: disable=invalid-name,protected-access,unused-argument,no-member
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

    @mock.patch.object(utils, "IsCommandRunning")
    def testFindLocalInstances(self, mock_command_running):
        """Test _FindLocalInstances."""
        mock_command_running.return_value = True
        expected_value = [delete._LOCAL_INS_NAME]
        self.assertEqual(expected_value, delete._FindLocalInstances())

        mock_command_running.return_value = False
        expected_value = []
        self.assertEqual(expected_value, delete._FindLocalInstances())

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("subprocess.check_output")
    def testGetStopcvd(self, mock_subprocess, mock_path_exist):
        """Test _GetStopCvd."""
        mock_subprocess.side_effect = ["fack_id",
                                       "/tmp/bin/launch_cvd --daemon --cpus 2"]
        expected_value = "/tmp/bin/stop_cvd"
        self.assertEqual(expected_value, delete._GetStopCvd())

    @mock.patch.object(delete, "_FindRemoteInstances")
    @mock.patch.object(delete, "_FindLocalInstances")
    def testGetInstancesToDelete(self, mock_local_instances, mock_remote_instances):
        """Test _GetInstancesToDelete."""
        cfg = mock.MagicMock()
        # Get remote and local instances.
        mock_remote_instances.return_value = ["ins-test-1"]
        mock_local_instances.return_value = ["local-instance"]
        expected_value = ["ins-test-1", "local-instance"]
        self.assertEqual(
            expected_value,
            delete._GetInstancesToDelete(cfg, del_all_instances=True))

        # Get remote instances.
        mock_remote_instances.return_value = ["ins-test-1"]
        mock_local_instances.return_value = []
        expected_value = ["ins-test-1"]
        self.assertEqual(expected_value, delete._GetInstancesToDelete(cfg))

        # Get local instances.
        mock_remote_instances.return_value = []
        mock_local_instances.return_value = ["local-instance"]
        expected_value = ["local-instance"]
        self.assertEqual(expected_value, delete._GetInstancesToDelete(cfg))

    @mock.patch.object(delete, "_GetStopCvd", return_value="")
    @mock.patch("subprocess.check_call")
    def testDeleteLocalInstance(self, mock_subprocess, mock_get_stopcvd):
        """Test DeleteLocalInstance."""
        mock_subprocess.return_value = True
        delete_report = delete.DeleteLocalInstance()
        self.assertEquals(delete_report.data, {
            "deleted": [
                {
                    "type": "instance",
                    "name": "local-instance",
                },
            ],
        })
        self.assertEquals(delete_report.command, "delete")
        self.assertEquals(delete_report.status, "SUCCESS")

    @mock.patch.object(delete, "DeleteLocalInstance")
    @mock.patch.object(device_driver, "DeleteAndroidVirtualDevices")
    def testDeleteInstances(self, mock_remote_delete, mock_local_delete):
        """Test DeleteInstances."""
        # Delete No instance.
        cfg = mock.MagicMock()
        instances_to_delete = []
        expected_value = None
        self.assertEqual(expected_value,
                         delete.DeleteInstances(cfg, instances_to_delete))

        # Delete local instance.
        instance_names = ["local-instance"]
        delete.DeleteInstances(cfg, instance_names)
        delete.DeleteLocalInstance.assert_called_once_with()

        # Delete remote instance.
        instance_names = ["fake-instance_1", "fake-instance_2"]
        delete.DeleteInstances(cfg, instance_names)
        device_driver.DeleteAndroidVirtualDevices.assert_called_once_with(
            cfg, instance_names, None)


if __name__ == "__main__":
    unittest.main()
