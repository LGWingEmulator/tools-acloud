#!/usr/bin/env python
#
# Copyright 2016 - The Android Open Source Project
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

"""Tests for acloud.public.config."""
import unittest
import os
import tempfile
import mock

# pylint: disable=no-name-in-module,import-error
from acloud.internal.proto import internal_config_pb2
from acloud.internal.proto import user_config_pb2
from acloud.public import config
from acloud.public import errors


class AcloudConfigManagerTest(unittest.TestCase):
    """Test acloud configuration manager."""

    USER_CONFIG = """
service_account_name: "fake@developer.gserviceaccount.com"
service_account_private_key_path: "/path/to/service/account/key"
service_account_json_private_key_path: "/path/to/service/account/json_key"
project: "fake-project"
zone: "us-central1-f"
machine_type: "n1-standard-1"
network: "default"
ssh_private_key_path: "/path/to/ssh/key"
storage_bucket_name: "fake_bucket"
orientation: "portrait"
resolution: "1200x1200x1200x1200"
client_id: "fake_client_id"
client_secret: "fake_client_secret"
metadata_variable {
    key: "metadata_1"
    value: "metadata_value_1"
}
"""

    INTERNAL_CONFIG = """
min_machine_size: "n1-standard-1"
disk_image_name: "avd-system.tar.gz"
disk_image_mime_type: "application/x-tar"
disk_image_extension: ".tar.gz"
disk_raw_image_name: "disk.raw"
disk_raw_image_extension: ".img"
creds_cache_file: ".fake_oauth2.dat"
user_agent: "fake_user_agent"
kernel_build_target: "kernel"
emulator_build_target: "sdk_tools_linux"

default_usr_cfg {
    machine_type: "n1-standard-1"
    network: "default"
    stable_host_image_name: "fake_stable_host_image_name"
    stable_host_image_project: "fake_stable_host_image_project"
    stable_goldfish_host_image_name: "fake_stable_goldfish_host_image_name"
    stable_goldfish_host_image_project: "fake_stable_goldfish_host_image_project"
    metadata_variable {
        key: "metadata_1"
        value: "metadata_value_1"
    }

    metadata_variable {
        key: "metadata_2"
        value: "metadata_value_2"
    }
}

device_resolution_map {
    key: "nexus5"
    value: "1080x1920x32x480"
}

device_default_orientation_map {
    key: "nexus5"
    value: "portrait"
}

valid_branch_and_min_build_id {
    key: "aosp-master"
    value: 0
}
"""

    def setUp(self):
        self.config_file = mock.MagicMock()

    # pylint: disable=no-member
    def testLoadUserConfig(self):
        """Test loading user config."""
        self.config_file.read.return_value = self.USER_CONFIG
        cfg = config.AcloudConfigManager.LoadConfigFromProtocolBuffer(
            self.config_file, user_config_pb2.UserConfig)
        self.assertEqual(cfg.service_account_name,
                         "fake@developer.gserviceaccount.com")
        self.assertEqual(cfg.service_account_private_key_path,
                         "/path/to/service/account/key")
        self.assertEqual(cfg.service_account_json_private_key_path,
                         "/path/to/service/account/json_key")
        self.assertEqual(cfg.project, "fake-project")
        self.assertEqual(cfg.zone, "us-central1-f")
        self.assertEqual(cfg.machine_type, "n1-standard-1")
        self.assertEqual(cfg.network, "default")
        self.assertEqual(cfg.ssh_private_key_path, "/path/to/ssh/key")
        self.assertEqual(cfg.storage_bucket_name, "fake_bucket")
        self.assertEqual(cfg.orientation, "portrait")
        self.assertEqual(cfg.resolution, "1200x1200x1200x1200")
        self.assertEqual(cfg.client_id, "fake_client_id")
        self.assertEqual(cfg.client_secret, "fake_client_secret")
        self.assertEqual(
            {key: val for key, val in cfg.metadata_variable.iteritems()},
            {"metadata_1": "metadata_value_1"})

    # pylint: disable=protected-access
    @mock.patch("os.path.exists")
    def testLoadUserConfigLogic(self, mock_file_exist):
        """Test load user config logic.

        Load user config with some special design.
        1. User specified user config:
            If user config didn't exist: Raise exception.
        2. User didn't specify user config, use default config:
            If default config didn't exist: Initialize empty data.
        """
        config_specify = config.AcloudConfigManager(self.config_file)
        self.config_file.read.return_value = self.USER_CONFIG
        self.assertEqual(config_specify._user_config_path, self.config_file)
        mock_file_exist.return_value = False
        with self.assertRaises(errors.ConfigError):
            config_specify.Load()
        # Test default config
        config_unspecify = config.AcloudConfigManager(None)
        cfg = config_unspecify.Load()
        self.assertEqual(config_unspecify._user_config_path,
                         config.GetDefaultConfigFile())
        self.assertEqual(cfg.project, "")
        self.assertEqual(cfg.zone, "")

        # Test default user config exist
        mock_file_exist.return_value = True
        # Write the config data into a tmp file and have GetDefaultConfigFile
        # return that.
        _, temp_cfg_file_path = tempfile.mkstemp()
        with open(temp_cfg_file_path, "w") as cfg_file:
            cfg_file.writelines(self.USER_CONFIG)
        default_patcher = mock.patch.object(config, "GetDefaultConfigFile",
                                            return_value=temp_cfg_file_path)
        default_patcher.start()
        try:
            config_exist = config.AcloudConfigManager(None)
            cfg = config_exist.Load()
            self.assertEqual(cfg.project, "fake-project")
            self.assertEqual(cfg.zone, "us-central1-f")
            self.assertEqual(cfg.client_id, "fake_client_id")
            self.assertEqual(cfg.client_secret, "fake_client_secret")
        finally:
            # Delete tmp file
            os.remove(temp_cfg_file_path)
            default_patcher.stop()

    def testLoadInternalConfig(self):
        """Test loading internal config."""
        self.config_file.read.return_value = self.INTERNAL_CONFIG
        cfg = config.AcloudConfigManager.LoadConfigFromProtocolBuffer(
            self.config_file, internal_config_pb2.InternalConfig)
        self.assertEqual(cfg.min_machine_size, "n1-standard-1")
        self.assertEqual(cfg.disk_image_name, "avd-system.tar.gz")
        self.assertEqual(cfg.disk_image_mime_type, "application/x-tar")
        self.assertEqual(cfg.disk_image_extension, ".tar.gz")
        self.assertEqual(cfg.disk_raw_image_name, "disk.raw")
        self.assertEqual(cfg.disk_raw_image_extension, ".img")
        self.assertEqual(cfg.creds_cache_file, ".fake_oauth2.dat")
        self.assertEqual(cfg.user_agent, "fake_user_agent")
        self.assertEqual(cfg.default_usr_cfg.machine_type, "n1-standard-1")
        self.assertEqual(cfg.default_usr_cfg.network, "default")
        self.assertEqual({
            key: val
            for key, val in cfg.default_usr_cfg.metadata_variable.iteritems()
        }, {
            "metadata_1": "metadata_value_1",
            "metadata_2": "metadata_value_2"
        })
        self.assertEqual(
            {key: val for key, val in cfg.device_resolution_map.iteritems()},
            {"nexus5": "1080x1920x32x480"})
        device_resolution = {
            key: val
            for key, val in cfg.device_default_orientation_map.iteritems()
        }
        self.assertEqual(device_resolution, {"nexus5": "portrait"})
        valid_branch_and_min_build_id = {
            key: val
            for key, val in cfg.valid_branch_and_min_build_id.iteritems()
        }
        self.assertEqual(valid_branch_and_min_build_id, {"aosp-master": 0})
        self.assertEqual(cfg.default_usr_cfg.stable_host_image_name,
                         "fake_stable_host_image_name")
        self.assertEqual(cfg.default_usr_cfg.stable_host_image_project,
                         "fake_stable_host_image_project")
        self.assertEqual(cfg.kernel_build_target, "kernel")

        # Emulator related
        self.assertEqual(cfg.default_usr_cfg.stable_goldfish_host_image_name,
                         "fake_stable_goldfish_host_image_name")
        self.assertEqual(cfg.default_usr_cfg.stable_goldfish_host_image_project,
                         "fake_stable_goldfish_host_image_project")
        self.assertEqual(cfg.emulator_build_target, "sdk_tools_linux")

    def testLoadConfigFails(self):
        """Test loading a bad file."""
        self.config_file.read.return_value = "malformed text"
        with self.assertRaises(errors.ConfigError):
            config.AcloudConfigManager.LoadConfigFromProtocolBuffer(
                self.config_file, internal_config_pb2.InternalConfig)


if __name__ == "__main__":
    unittest.main()
