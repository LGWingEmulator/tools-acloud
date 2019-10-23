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
"""Tests for remote_instance_cf_device_factory."""

import glob
import os
import unittest
import uuid

import mock

from acloud.create import avd_spec
from acloud.internal import constants
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.internal.lib import cvd_compute_client_multi_stage
from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils
from acloud.list import list as list_instances
from acloud.public.actions import remote_instance_cf_device_factory


class RemoteInstanceDeviceFactoryTest(driver_test_lib.BaseDriverTest):
    """Test RemoteInstanceDeviceFactory method."""

    def setUp(self):
        """Set up the test."""
        super(RemoteInstanceDeviceFactoryTest, self).setUp()
        self.Patch(auth, "CreateCredentials", return_value=mock.MagicMock())
        self.Patch(android_build_client.AndroidBuildClient, "InitResourceHandle")
        self.Patch(cvd_compute_client_multi_stage.CvdComputeClient, "InitResourceHandle")
        self.Patch(list_instances, "GetInstancesFromInstanceNames", return_value=mock.MagicMock())
        self.Patch(list_instances, "ChooseOneRemoteInstance", return_value=mock.MagicMock())
        self.Patch(utils, "GetBuildEnvironmentVariable",
                   return_value="test_environ")
        self.Patch(glob, "glob", return_vale=["fake.img"])

    # pylint: disable=protected-access
    @mock.patch.object(remote_instance_cf_device_factory.RemoteInstanceDeviceFactory,
                       "_FetchBuild")
    @mock.patch.object(remote_instance_cf_device_factory.RemoteInstanceDeviceFactory,
                       "_UploadArtifacts")
    def testProcessArtifacts(self, mock_upload, mock_download):
        """test ProcessArtifacts."""
        # Test image source type is local.
        args = mock.MagicMock()
        args.config_file = ""
        args.avd_type = constants.TYPE_CF
        args.flavor = "phone"
        args.local_image = None
        avd_spec_local_img = avd_spec.AVDSpec(args)
        fake_image_name = "/fake/aosp_cf_x86_phone-img-eng.username.zip"
        fake_host_package_name = "/fake/host_package.tar.gz"
        factory_local_img = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            avd_spec_local_img,
            fake_image_name,
            fake_host_package_name)
        factory_local_img._ProcessArtifacts(constants.IMAGE_SRC_LOCAL)
        self.assertEqual(mock_upload.call_count, 1)

        # Test image source type is remote.
        args.local_image = ""
        args.build_id = "1234"
        args.branch = "fake_branch"
        args.build_target = "fake_target"
        args.system_build_id = "2345"
        args.system_branch = "sys_branch"
        args.system_build_target = "sys_target"
        args.kernel_build_id = "3456"
        args.kernel_branch = "kernel_branch"
        args.kernel_build_target = "kernel_target"
        avd_spec_remote_img = avd_spec.AVDSpec(args)
        self.Patch(cvd_compute_client_multi_stage.CvdComputeClient, "UpdateFetchCvd")
        factory_remote_img = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            avd_spec_remote_img)
        factory_remote_img._ProcessArtifacts(constants.IMAGE_SRC_REMOTE)
        self.assertEqual(mock_download.call_count, 1)

    # pylint: disable=protected-access
    @mock.patch.dict(os.environ, {constants.ENV_BUILD_TARGET:'fake-target'})
    def testCreateGceInstanceNameMultiStage(self):
        """test create gce instance."""
        # Mock uuid
        args = mock.MagicMock()
        args.config_file = ""
        args.avd_type = constants.TYPE_CF
        args.flavor = "phone"
        args.local_image = None
        args.adb_port = None
        fake_avd_spec = avd_spec.AVDSpec(args)
        fake_avd_spec.cfg.enable_multi_stage = True
        fake_avd_spec._instance_name_to_reuse = None

        fake_uuid = mock.MagicMock(hex="1234")
        self.Patch(uuid, "uuid4", return_value=fake_uuid)
        self.Patch(cvd_compute_client_multi_stage.CvdComputeClient, "CreateInstance")
        fake_host_package_name = "/fake/host_package.tar.gz"
        fake_image_name = "/fake/aosp_cf_x86_phone-img-eng.username.zip"

        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-aosp-cf-x86-phone")

        # Can't get target name from zip file name.
        fake_image_name = "/fake/aosp_cf_x86_phone.username.zip"
        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-fake-target")

        # No image zip path, it uses local build images.
        fake_image_name = ""
        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "ins-1234-userbuild-fake-target")

    def testReuseInstanceNameMultiStage(self):
        """Test reuse instance name."""
        args = mock.MagicMock()
        args.config_file = ""
        args.avd_type = constants.TYPE_CF
        args.flavor = "phone"
        args.local_image = None
        args.adb_port = None
        fake_avd_spec = avd_spec.AVDSpec(args)
        fake_avd_spec.cfg.enable_multi_stage = True
        fake_avd_spec._instance_name_to_reuse = "fake-1234-userbuild-fake-target"
        fake_uuid = mock.MagicMock(hex="1234")
        self.Patch(uuid, "uuid4", return_value=fake_uuid)
        self.Patch(cvd_compute_client_multi_stage.CvdComputeClient, "CreateInstance")
        fake_host_package_name = "/fake/host_package.tar.gz"
        fake_image_name = "/fake/aosp_cf_x86_phone-img-eng.username.zip"
        factory = remote_instance_cf_device_factory.RemoteInstanceDeviceFactory(
            fake_avd_spec,
            fake_image_name,
            fake_host_package_name)
        self.assertEqual(factory._CreateGceInstance(), "fake-1234-userbuild-fake-target")


if __name__ == "__main__":
    unittest.main()
