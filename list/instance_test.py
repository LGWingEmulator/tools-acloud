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
"""Tests for host_setup_runner."""
import collections
import subprocess

import unittest

from acloud.internal import constants
from acloud.internal.lib import driver_test_lib
from acloud.list import instance


class InstanceTest(driver_test_lib.BaseDriverTest):
    """Test instance."""
    PS_SSH_TUNNEL = ("/fake_ps_1 --fake arg \n"
                     "/fake_ps_2 --fake arg \n"
                     "/usr/bin/ssh -i ~/.ssh/acloud_rsa "
                     "-o UserKnownHostsFile=/dev/null "
                     "-o StrictHostKeyChecking=no -L 12345:127.0.0.1:6444 "
                     "-L 54321:127.0.0.1:6520 -N -f -l user fake_ip")
    PS_LAUNCH_CVD = ("Sat Nov 10 21:55:10 2018 /fake_path/bin/launch_cvd "
                     "--daemon --cpus 2 --x_res 1080 --y_res 1920 --dpi 480"
                     " --memory_mb 4096 --blank_data_image_mb 4096 --data_policy"
                     " always_create --system_image_dir /fake "
                     "--vnc_server_port 6444")

    # pylint: disable=protected-access
    def testCreateLocalInstance(self):
        """"Test get local instance info from launch_cvd process."""
        self.Patch(subprocess, "check_output", return_value=self.PS_LAUNCH_CVD)
        local_instance = instance.LocalInstance()
        self.assertEqual(constants.LOCAL_INS_NAME, local_instance.name)
        self.assertEqual(True, local_instance.islocal)
        self.assertEqual("1080x1920 (480)", local_instance.display)
        self.assertEqual("Sat Nov 10 21:55:10 2018", local_instance.createtime)
        expected_full_name = "device serial: 127.0.0.1:%s (%s)" % (constants.DEFAULT_ADB_PORT,
                                                                   local_instance.name)
        self.assertEqual(expected_full_name, local_instance.fullname)

        # test return None if no launch_cvd process found
        self.Patch(subprocess, "check_output", return_value="no launch_cvd "
                                                            "found")
        self.assertEqual(None, instance.LocalInstance())

    # pylint: disable=protected-access
    def testGetAdbVncPortFromSSHTunnel(self):
        """"Test Get forwarding adb and vnc port from ssh tunnel."""
        self.Patch(subprocess, "check_output", return_value=self.PS_SSH_TUNNEL)
        forwarded_ports = instance.RemoteInstance._GetAdbVncPortFromSSHTunnel("fake_ip")
        self.assertEqual(54321, forwarded_ports.adb_port)
        self.assertEqual(12345, forwarded_ports.vnc_port)

    # pylint: disable=protected-access
    def testProcessGceInstance(self):
        """"Test process instance detail."""
        gce_instance = {
            constants.INS_KEY_NAME: "fake_ins_name",
            constants.INS_KEY_CREATETIME: "fake_create_time",
            constants.INS_KEY_STATUS: "fake_status",
            "networkInterfaces": [{"accessConfigs": [{"natIP": "fake_ip"}]}],
            "labels": {constants.INS_KEY_AVD_TYPE: "fake_type",
                       constants.INS_KEY_AVD_FLAVOR: "fake_flavor"},
            "metadata": {}
        }

        fake_adb = 123456
        fake_vnc = 654321
        forwarded_ports = collections.namedtuple("ForwardedPorts",
                                                 [constants.VNC_PORT,
                                                  constants.ADB_PORT])
        self.Patch(
            instance.RemoteInstance,
            "_GetAdbVncPortFromSSHTunnel",
            return_value=forwarded_ports(vnc_port=fake_vnc, adb_port=fake_adb))

        # test is_connected will be true if ssh tunnel connection is found
        instance_info = instance.RemoteInstance(gce_instance)
        self.assertTrue(instance_info.is_connected)
        self.assertEqual(instance_info.forwarding_adb_port, fake_adb)
        self.assertEqual(instance_info.forwarding_vnc_port, fake_vnc)
        expected_full_name = "device serial: 127.0.0.1:%s (%s)" % (fake_adb,
                                                                   instance_info.name)
        self.assertEqual(expected_full_name, instance_info.fullname)

        # test is_connected will be false if ssh tunnel connection is not found
        self.Patch(
            instance.RemoteInstance,
            "_GetAdbVncPortFromSSHTunnel",
            return_value=forwarded_ports(vnc_port=None, adb_port=None))
        instance_info = instance.RemoteInstance(gce_instance)
        self.assertFalse(instance_info.is_connected)
        expected_full_name = ("device serial: not connected (%s)" %
                              instance_info.name)
        self.assertEqual(expected_full_name, instance_info.fullname)


if __name__ == "__main__":
    unittest.main()
