#!/usr/bin/env python
#
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
"""Tests for instance class."""

import collections
import datetime
import os
import subprocess

import unittest
import mock
import six

# pylint: disable=import-error
import dateutil.parser
import dateutil.tz

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib.adb_tools import AdbTools
from acloud.list import instance


class InstanceTest(driver_test_lib.BaseDriverTest):
    """Test instance."""
    PS_SSH_TUNNEL = ("/fake_ps_1 --fake arg \n"
                     "/fake_ps_2 --fake arg \n"
                     "/usr/bin/ssh -i ~/.ssh/acloud_rsa "
                     "-o UserKnownHostsFile=/dev/null "
                     "-o StrictHostKeyChecking=no -L 12345:127.0.0.1:6444 "
                     "-L 54321:127.0.0.1:6520 -N -f -l user 1.1.1.1")
    PS_LAUNCH_CVD = ("Sat Nov 10 21:55:10 2018 /fake_path/bin/run_cvd ")
    PS_RUNTIME_CF_CONFIG = {"x_res": "1080", "y_res": "1920", "dpi": "480"}
    GCE_INSTANCE = {
        constants.INS_KEY_NAME: "fake_ins_name",
        constants.INS_KEY_CREATETIME: "fake_create_time",
        constants.INS_KEY_STATUS: "fake_status",
        "networkInterfaces": [{"accessConfigs": [{"natIP": "1.1.1.1"}]}],
        "labels": {constants.INS_KEY_AVD_TYPE: "fake_type",
                   constants.INS_KEY_AVD_FLAVOR: "fake_flavor"},
        "metadata": {
            "items":[{"key":constants.INS_KEY_AVD_TYPE,
                      "value":"fake_type"},
                     {"key":constants.INS_KEY_AVD_FLAVOR,
                      "value":"fake_flavor"}]}
    }

    # pylint: disable=protected-access
    def testCreateLocalInstance(self):
        """"Test get local instance info from launch_cvd process."""
        self.Patch(subprocess, "check_output", return_value=self.PS_LAUNCH_CVD)
        self.Patch(instance, "_GetElapsedTime", return_value="fake_time")
        local_instance = instance.LocalInstance(2,
                                                "1080",
                                                "1920",
                                                "480",
                                                "Sat Nov 10 21:55:10 2018",
                                                "fake_instance_dir")

        self.assertEqual(constants.LOCAL_INS_NAME + "-2", local_instance.name)
        self.assertEqual(True, local_instance.islocal)
        self.assertEqual("1080x1920 (480)", local_instance.display)
        self.assertEqual("Sat Nov 10 21:55:10 2018", local_instance.createtime)
        expected_full_name = ("device serial: 127.0.0.1:%s (%s) elapsed time: %s"
                              % ("6521",
                                 constants.LOCAL_INS_NAME + "-2",
                                 "fake_time"))
        self.assertEqual(expected_full_name, local_instance.fullname)
        self.assertEqual(6521, local_instance.forwarding_adb_port)
        self.assertEqual(6445, local_instance.forwarding_vnc_port)

    def testGetElapsedTime(self):
        """Test _GetElapsedTime"""
        # Instance time can't parse
        start_time = "error time"
        self.assertEqual(instance._MSG_UNABLE_TO_CALCULATE,
                         instance._GetElapsedTime(start_time))

        # Remote instance elapsed time
        now = "2019-01-14T13:00:00.000-07:00"
        start_time = "2019-01-14T03:00:00.000-07:00"
        self.Patch(instance, "datetime")
        instance.datetime.datetime.now.return_value = dateutil.parser.parse(now)
        self.assertEqual(
            datetime.timedelta(hours=10), instance._GetElapsedTime(start_time))

        # Local instance elapsed time
        now = "Mon Jan 14 10:10:10 2019"
        start_time = "Mon Jan 14 08:10:10 2019"
        instance.datetime.datetime.now.return_value = dateutil.parser.parse(
            now).replace(tzinfo=dateutil.tz.tzlocal())
        self.assertEqual(
            datetime.timedelta(hours=2), instance._GetElapsedTime(start_time))

    # pylint: disable=protected-access
    def testGetAdbVncPortFromSSHTunnel(self):
        """"Test Get forwarding adb and vnc port from ssh tunnel."""
        self.Patch(subprocess, "check_output", return_value=self.PS_SSH_TUNNEL)
        self.Patch(instance, "_GetElapsedTime", return_value="fake_time")
        forwarded_ports = instance.RemoteInstance(
            mock.MagicMock()).GetAdbVncPortFromSSHTunnel(
                "1.1.1.1", constants.TYPE_CF)
        self.assertEqual(54321, forwarded_ports.adb_port)
        self.assertEqual(12345, forwarded_ports.vnc_port)

        # If avd_type is undefined in utils.AVD_PORT_DICT.
        forwarded_ports = instance.RemoteInstance(
            mock.MagicMock()).GetAdbVncPortFromSSHTunnel(
                "1.1.1.1", "undefined_avd_type")
        self.assertEqual(None, forwarded_ports.adb_port)
        self.assertEqual(None, forwarded_ports.vnc_port)

    # pylint: disable=protected-access
    def testProcessGceInstance(self):
        """"Test process instance detail."""
        fake_adb = 123456
        fake_vnc = 654321
        forwarded_ports = collections.namedtuple("ForwardedPorts",
                                                 [constants.VNC_PORT,
                                                  constants.ADB_PORT])
        self.Patch(
            instance.RemoteInstance,
            "GetAdbVncPortFromSSHTunnel",
            return_value=forwarded_ports(vnc_port=fake_vnc, adb_port=fake_adb))
        self.Patch(instance, "_GetElapsedTime", return_value="fake_time")
        self.Patch(AdbTools, "IsAdbConnected", return_value=True)

        # test ssh_tunnel_is_connected will be true if ssh tunnel connection is found
        instance_info = instance.RemoteInstance(self.GCE_INSTANCE)
        self.assertTrue(instance_info.ssh_tunnel_is_connected)
        self.assertEqual(instance_info.forwarding_adb_port, fake_adb)
        self.assertEqual(instance_info.forwarding_vnc_port, fake_vnc)
        self.assertEqual("1.1.1.1", instance_info.ip)
        self.assertEqual("fake_status", instance_info.status)
        self.assertEqual("fake_type", instance_info.avd_type)
        self.assertEqual("fake_flavor", instance_info.avd_flavor)
        expected_full_name = "device serial: 127.0.0.1:%s (%s) elapsed time: %s" % (
            fake_adb, self.GCE_INSTANCE[constants.INS_KEY_NAME], "fake_time")
        self.assertEqual(expected_full_name, instance_info.fullname)

        # test ssh tunnel is connected but adb is disconnected
        self.Patch(AdbTools, "IsAdbConnected", return_value=False)
        instance_info = instance.RemoteInstance(self.GCE_INSTANCE)
        self.assertTrue(instance_info.ssh_tunnel_is_connected)
        expected_full_name = "device serial: not connected (%s) elapsed time: %s" % (
            instance_info.name, "fake_time")
        self.assertEqual(expected_full_name, instance_info.fullname)

        # test ssh_tunnel_is_connected will be false if ssh tunnel connection is not found
        self.Patch(
            instance.RemoteInstance,
            "GetAdbVncPortFromSSHTunnel",
            return_value=forwarded_ports(vnc_port=None, adb_port=None))
        instance_info = instance.RemoteInstance(self.GCE_INSTANCE)
        self.assertFalse(instance_info.ssh_tunnel_is_connected)
        expected_full_name = "device serial: not connected (%s) elapsed time: %s" % (
            self.GCE_INSTANCE[constants.INS_KEY_NAME], "fake_time")
        self.assertEqual(expected_full_name, instance_info.fullname)

    def testInstanceSummary(self):
        """Test instance summary."""
        fake_adb = 123456
        fake_vnc = 654321
        forwarded_ports = collections.namedtuple("ForwardedPorts",
                                                 [constants.VNC_PORT,
                                                  constants.ADB_PORT])
        self.Patch(
            instance.RemoteInstance,
            "GetAdbVncPortFromSSHTunnel",
            return_value=forwarded_ports(vnc_port=fake_vnc, adb_port=fake_adb))
        self.Patch(instance, "_GetElapsedTime", return_value="fake_time")
        self.Patch(AdbTools, "IsAdbConnected", return_value=True)
        remote_instance = instance.RemoteInstance(self.GCE_INSTANCE)
        result_summary = (" name: fake_ins_name\n "
                          "   IP: 1.1.1.1\n "
                          "   create time: fake_create_time\n "
                          "   elapse time: fake_time\n "
                          "   status: fake_status\n "
                          "   avd type: fake_type\n "
                          "   display: None\n "
                          "   vnc: 127.0.0.1:654321\n "
                          "   adb serial: 127.0.0.1:123456\n "
                          "   product: None\n "
                          "   model: None\n "
                          "   device: None\n "
                          "   transport_id: None")
        self.assertEqual(remote_instance.Summary(), result_summary)

        self.Patch(
            instance.RemoteInstance,
            "GetAdbVncPortFromSSHTunnel",
            return_value=forwarded_ports(vnc_port=None, adb_port=None))
        self.Patch(instance, "_GetElapsedTime", return_value="fake_time")
        self.Patch(AdbTools, "IsAdbConnected", return_value=False)
        remote_instance = instance.RemoteInstance(self.GCE_INSTANCE)
        result_summary = (" name: fake_ins_name\n "
                          "   IP: 1.1.1.1\n "
                          "   create time: fake_create_time\n "
                          "   elapse time: fake_time\n "
                          "   status: fake_status\n "
                          "   avd type: fake_type\n "
                          "   display: None\n "
                          "   vnc: 127.0.0.1:None\n "
                          "   adb serial: disconnected")
        self.assertEqual(remote_instance.Summary(), result_summary)

    def testGetCuttlefishRuntimeConfig(self):
        """Test GetCuttlefishRuntimeConfig."""
        # Should raise error when file does not exist.
        self.Patch(os.path, "exists", return_value=False)
        self.assertRaises(errors.ConfigError, instance.GetCuttlefishRuntimeConfig, 9)
        # Verify return data.
        self.Patch(os.path, "exists", return_value=True)
        fake_runtime_cf_config = ("{\"x_display\" : \":20\",\"x_res\" : 720,\"y_res\" : 1280}")
        mock_open = mock.mock_open(read_data=fake_runtime_cf_config)
        with mock.patch.object(six.moves.builtins, "open", mock_open):
            self.assertEqual({u'y_res': 1280, u'x_res': 720, u'x_display': u':20'},
                             instance.GetCuttlefishRuntimeConfig(1))


if __name__ == "__main__":
    unittest.main()
