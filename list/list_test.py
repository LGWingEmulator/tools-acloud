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
"""Tests for list."""
import unittest

import mock

from acloud import errors
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils
from acloud.list import list as list_instance


class InstanceObject(object):
    """Mock to store data of instance."""

    def __init__(self, name):
        self.name = name


class ListTest(driver_test_lib.BaseDriverTest):
    """Test list."""

    def testGetInstancesFromInstanceNames(self):
        """test get instances from instance names."""
        cfg = mock.MagicMock()
        instance_names = ["alive_instance1", "alive_local_instance"]

        alive_instance1 = InstanceObject("alive_instance1")
        alive_instance2 = InstanceObject("alive_instance2")
        alive_local_instance = InstanceObject("alive_local_instance")

        instance_alive = [alive_instance1, alive_instance2, alive_local_instance]
        self.Patch(list_instance, "GetInstances", return_value=instance_alive)
        instances_list = list_instance.GetInstancesFromInstanceNames(cfg, instance_names)
        instances_name_in_list = [instance_object.name for instance_object in instances_list]
        self.assertEqual(instances_name_in_list.sort(), instance_names.sort())

        instance_names = ["alive_instance1", "alive_local_instance", "alive_local_instance"]
        instances_list = list_instance.GetInstancesFromInstanceNames(cfg, instance_names)
        instances_name_in_list = [instance_object.name for instance_object in instances_list]
        self.assertEqual(instances_name_in_list.sort(), instance_names.sort())

        # test get instance from instance name error with invalid input.
        instance_names = ["miss2_local_instance", "alive_instance1"]
        miss_instance_names = ["miss2_local_instance"]
        self.assertRaisesRegexp(
            errors.NoInstancesFound,
            "Did not find the following instances: %s" % ' '.join(miss_instance_names),
            list_instance.GetInstancesFromInstanceNames,
            cfg=cfg,
            instance_names=instance_names)

    def testChooseOneRemoteInstance(self):
        """test choose one remote instance from instance names."""
        cfg = mock.MagicMock()

        # Test only one instance case
        instance_names = ["cf_instance1"]
        self.Patch(list_instance, "GetCFRemoteInstances", return_value=instance_names)
        expected_instance = "cf_instance1"
        self.assertEqual(list_instance.ChooseOneRemoteInstance(cfg), expected_instance)

        # Test no instance case
        self.Patch(list_instance, "GetCFRemoteInstances", return_value=[])
        with self.assertRaises(errors.NoInstancesFound):
            list_instance.ChooseOneRemoteInstance(cfg)

        # Test two instances case.
        instance_names = ["cf_instance1", "cf_instance2"]
        choose_instance = ["cf_instance2"]
        self.Patch(list_instance, "GetCFRemoteInstances", return_value=instance_names)
        self.Patch(utils, "GetAnswerFromList", return_value=choose_instance)
        expected_instance = "cf_instance2"
        self.assertEqual(list_instance.ChooseOneRemoteInstance(cfg), expected_instance)

    # pylint: disable=attribute-defined-outside-init
    def testGetInstanceFromAdbPort(self):
        """test GetInstanceFromAdbPort."""
        cfg = mock.MagicMock()
        alive_instance1 = InstanceObject("alive_instance1")
        alive_instance1.forwarding_adb_port = 1111
        alive_instance1.fullname = "device serial: 127.0.0.1:1111 alive_instance1"
        expected_instance = [alive_instance1]
        self.Patch(list_instance, "GetInstances", return_value=[alive_instance1])
        # Test to find instance by adb port number.
        self.assertEqual(expected_instance,
                         list_instance.GetInstanceFromAdbPort(cfg, 1111))
        # Test for instance can't be found by adb port number.
        with self.assertRaises(errors.NoInstancesFound):
            list_instance.GetInstanceFromAdbPort(cfg, 2222)


if __name__ == "__main__":
    unittest.main()
