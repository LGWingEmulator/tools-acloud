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
"""Tests for reconnect."""

import collections
import getpass
import unittest
import subprocess

import mock

from acloud.internal import constants
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils
from acloud.reconnect import reconnect

ForwardedPorts = collections.namedtuple("ForwardedPorts",
                                        [constants.VNC_PORT, constants.ADB_PORT])


class ReconnectTest(driver_test_lib.BaseDriverTest):
    """Test reconnect functions."""

    # pylint: disable=no-member
    def testReconnectInstance(self):
        """Test Reconnect Instances."""
        ssh_private_key_path = "/fake/acloud_rea"
        instance_object = mock.MagicMock()
        instance_object.ip = "1.1.1.1"
        instance_object.islocal = False
        instance_object.forwarding_adb_port = "8686"
        self.Patch(getpass, "getuser", return_value="fake_user")
        self.Patch(subprocess, "check_call", return_value=True)
        self.Patch(utils, "LaunchVncClient")
        self.Patch(utils, "AutoConnect")
        self.Patch(reconnect.AdbTools, "IsAdbConnected", return_value=False)
        self.Patch(reconnect.AdbTools, "IsAdbConnectionAlive", return_value=False)
        self.Patch(utils, "IsCommandRunning", return_value=False)

        #test ssh tunnel not connected, remote instance.
        instance_object.forwarding_vnc_port = 6666
        instance_object.display = ""
        utils.AutoConnect.call_count = 0
        reconnect.ReconnectInstance(ssh_private_key_path, instance_object)
        utils.AutoConnect.assert_not_called()
        utils.LaunchVncClient.assert_called_with(6666)

        instance_object.display = "888x777 (99)"
        utils.AutoConnect.call_count = 0
        reconnect.ReconnectInstance(ssh_private_key_path, instance_object)
        utils.AutoConnect.assert_not_called()
        utils.LaunchVncClient.assert_called_with(6666, "888", "777")

        #test ssh tunnel connected , remote instance.
        instance_object.ssh_tunnel_is_connected = False
        instance_object.display = ""
        utils.AutoConnect.call_count = 0
        instance_object.forwarding_vnc_port = 5555
        self.Patch(utils, "AutoConnect",
                   return_value=ForwardedPorts(vnc_port=11111, adb_port=22222))
        reconnect.ReconnectInstance(ssh_private_key_path, instance_object)
        utils.AutoConnect.assert_called_with(instance_object.ip,
                                             ssh_private_key_path,
                                             constants.CF_TARGET_VNC_PORT,
                                             constants.CF_TARGET_ADB_PORT,
                                             "fake_user")
        utils.LaunchVncClient.assert_called_with(11111)

        instance_object.display = "999x777 (99)"
        utils.AutoConnect.call_count = 0
        reconnect.ReconnectInstance(ssh_private_key_path, instance_object)
        utils.AutoConnect.assert_called_with(instance_object.ip,
                                             ssh_private_key_path,
                                             constants.CF_TARGET_VNC_PORT,
                                             constants.CF_TARGET_ADB_PORT,
                                             "fake_user")
        utils.LaunchVncClient.assert_called_with(11111, "999", "777")

        #test reconnect local instance.
        instance_object.islocal = True
        instance_object.display = ""
        instance_object.forwarding_vnc_port = 5555
        instance_object.ssh_tunnel_is_connected = False
        utils.AutoConnect.call_count = 0
        reconnect.ReconnectInstance(ssh_private_key_path, instance_object)
        utils.AutoConnect.assert_not_called()
        utils.LaunchVncClient.assert_called_with(5555)

    def testStartVnc(self):
        """Test start Vnc."""
        self.Patch(subprocess, "check_call", return_value=True)
        self.Patch(utils, "IsCommandRunning", return_value=False)
        self.Patch(utils, "LaunchVncClient")
        vnc_port = 5555
        display = ""
        reconnect.StartVnc(vnc_port, display)
        utils.LaunchVncClient.assert_called_with(5555)

        display = "888x777 (99)"
        utils.AutoConnect.call_count = 0
        reconnect.StartVnc(vnc_port, display)
        utils.LaunchVncClient.assert_called_with(5555, "888", "777")

    # pylint: disable=protected-access, no-member
    def testCleanupSSVncviwer(self):
        """test cleanup ssvnc viewer."""
        fake_vnc_port = 9999
        fake_ss_vncviewer_pattern = reconnect._SSVNC_VIEWER_PATTERN % {
            "vnc_port": fake_vnc_port}
        self.Patch(utils, "IsCommandRunning", return_value=True)
        self.Patch(subprocess, "check_call", return_value=True)
        reconnect.CleanupSSVncviewer(fake_ss_vncviewer_pattern)
        subprocess.check_call.assert_called_with(['pkill', '-9', '-f', fake_ss_vncviewer_pattern])

        subprocess.check_call.call_count = 0
        self.Patch(utils, "IsCommandRunning", return_value=False)
        subprocess.check_call.assert_not_called()


class AdbToolsTest(driver_test_lib.BaseDriverTest):
    """Test adb functions."""
    DEVICE_ALIVE = ("List of devices attached\n"
                    "127.0.0.1:48451 device")
    DEVICE_OFFLINE = ("List of devices attached\n"
                      "127.0.0.1:48451 offline")
    DEVICE_NONE = ("List of devices attached")

    # pylint: disable=no-member
    def testGetAdbConnectionStatus(self):
        """Test get adb connection status."""
        fake_adb_port = "48451"
        self.Patch(subprocess, "check_output", return_value=self.DEVICE_ALIVE)
        adb_cmd = reconnect.AdbTools(fake_adb_port)
        self.assertEqual(adb_cmd.GetAdbConnectionStatus(), "device")

        self.Patch(subprocess, "check_output", return_value=self.DEVICE_OFFLINE)
        self.assertEqual(adb_cmd.GetAdbConnectionStatus(), "offline")

        self.Patch(subprocess, "check_output", return_value=self.DEVICE_NONE)
        self.assertEqual(adb_cmd.GetAdbConnectionStatus(), None)

    # pylint: disable=no-member,protected-access
    def testConnectAdb(self):
        """Test connect adb."""
        fake_adb_port = "48451"
        self.Patch(subprocess, "check_output", return_value=self.DEVICE_ALIVE)
        self.Patch(subprocess, "check_call", return_value=True)
        adb_cmd = reconnect.AdbTools(fake_adb_port)
        adb_cmd.ConnectAdb()
        self.assertEqual(adb_cmd.IsAdbConnectionAlive(), True)
        subprocess.check_call.assert_not_called()

        self.Patch(subprocess, "check_output", return_value=self.DEVICE_OFFLINE)
        self.Patch(subprocess, "check_call", return_value=True)
        subprocess.check_call.call_count = 0
        adb_cmd = reconnect.AdbTools(fake_adb_port)
        adb_cmd.ConnectAdb()
        self.assertEqual(adb_cmd.IsAdbConnectionAlive(), False)
        subprocess.check_call.assert_called_with([adb_cmd._adb_command,
                                                  reconnect._ADB_CONNECT,
                                                  adb_cmd._device_serial])

    # pylint: disable=no-member,protected-access
    def testDisconnectAdb(self):
        """Test disconnect adb."""
        fake_adb_port = "48451"
        self.Patch(subprocess, "check_output", return_value=self.DEVICE_ALIVE)
        self.Patch(subprocess, "check_call", return_value=True)
        adb_cmd = reconnect.AdbTools(fake_adb_port)

        self.assertEqual(adb_cmd.IsAdbConnected(), True)
        subprocess.check_call.assert_not_called()

        self.Patch(subprocess, "check_output", return_value=self.DEVICE_OFFLINE)
        self.Patch(subprocess, "check_call", return_value=True)
        subprocess.check_call.call_count = 0
        adb_cmd = reconnect.AdbTools(fake_adb_port)
        adb_cmd.DisconnectAdb()
        self.assertEqual(adb_cmd.IsAdbConnected(), True)
        subprocess.check_call.assert_called_with([adb_cmd._adb_command,
                                                  reconnect._ADB_DISCONNECT,
                                                  adb_cmd._device_serial])

        self.Patch(subprocess, "check_output", return_value=self.DEVICE_NONE)
        self.Patch(subprocess, "check_call", return_value=True)
        subprocess.check_call.call_count = 0
        adb_cmd = reconnect.AdbTools(fake_adb_port)
        adb_cmd.DisconnectAdb()
        self.assertEqual(adb_cmd.IsAdbConnected(), False)
        subprocess.check_call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
