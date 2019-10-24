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
"""Tests for GoldfishLocalImageLocalInstance."""

import os
import shutil
import tempfile
import unittest
import mock

import acloud.create.goldfish_local_image_local_instance as instance_module


class GoldfishLocalImageLocalInstance(unittest.TestCase):
    """Test GoldfishLocalImageLocalInstance methods."""

    def setUp(self):
        self._goldfish = instance_module.GoldfishLocalImageLocalInstance()
        self._temp_dir = tempfile.mkdtemp()
        self._image_dir = os.path.join(self._temp_dir, "images")
        self._emulator_is_running = False
        self._mock_proc = mock.Mock()
        self._mock_proc.poll.side_effect = (
            lambda: None if self._emulator_is_running else 0)

        os.mkdir(self._image_dir)

        # Create emulator binary
        os.mkdir(os.path.join(self._temp_dir, "emulator"))
        self._emulator_path = os.path.join(self._temp_dir, "emulator",
                                           "emulator")
        self._CreateEmptyFile(self._emulator_path)

    def tearDown(self):
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    @staticmethod
    def _CreateEmptyFile(path):
        parent_dir = os.path.dirname(path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        with open(path, "w") as _:
            pass

    def _MockPopen(self, *_args, **_kwargs):
        self._emulator_is_running = True
        return self._mock_proc

    def _MockEmuCommand(self, *args):
        if not self._emulator_is_running:
            # Connection refused
            return 1

        if args == ("kill",):
            self._emulator_is_running = False
            return 0

        if args == ():
            return 0

        raise ValueError("Unexpected arguments " + str(args))

    def _SetUpMocks(self, mock_popen, mock_adb_tools, mock_utils,
                    mock_temp_file):
        mock_temp_file.gettempdir.return_value = self._temp_dir
        mock_utils.IsSupportedPlatform.return_value = True

        mock_adb_tools_object = mock.Mock()
        mock_adb_tools_object.EmuCommand.side_effect = self._MockEmuCommand
        mock_adb_tools.return_value = mock_adb_tools_object

        mock_popen.side_effect = self._MockPopen

    # pylint: disable=protected-access
    @mock.patch("acloud.create.goldfish_local_image_local_instance.tempfile")
    @mock.patch("acloud.create.goldfish_local_image_local_instance.utils")
    @mock.patch("acloud.create.goldfish_local_image_local_instance."
                "adb_tools.AdbTools")
    @mock.patch("acloud.create.goldfish_local_image_local_instance."
                "subprocess.Popen")
    def testCreateAVDInBuildEnvironment(self, mock_popen, mock_adb_tools,
                                        mock_utils, mock_temp_file):
        """Test _CreateAVD with build environment variables and files."""
        self._SetUpMocks(mock_popen, mock_adb_tools, mock_utils,
                         mock_temp_file)

        self._CreateEmptyFile(os.path.join(self._image_dir, "system.img"))
        self._CreateEmptyFile(os.path.join(self._image_dir, "system",
                                           "build.prop"))

        mock_environ = {"ANDROID_EMULATOR_PREBUILTS":
                        os.path.join(self._temp_dir, "emulator")}

        mock_avd_spec = mock.Mock(local_instance_id=1,
                                  local_image_dir=self._image_dir)

        # Test deleting an existing instance.
        self._emulator_is_running = True

        with mock.patch.dict("acloud.create."
                             "goldfish_local_image_local_instance.os.environ",
                             mock_environ, clear=True):
            self._goldfish._CreateAVD(mock_avd_spec, no_prompts=False)

        instance_dir = os.path.join(self._temp_dir, "acloud_gf_temp",
                                    "instance-1")
        expected_cmd = [
            self._emulator_path, "-verbose", "-show-kernel", "-read-only",
            "-ports", "5554,5555",
            "-logcat-output", os.path.join(instance_dir, "logcat.txt"),
            "-stdouterr-file", os.path.join(instance_dir, "stdouterr.txt")
        ]
        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args[0][0], expected_cmd)
        self._mock_proc.poll.assert_called()

    # pylint: disable=protected-access
    @mock.patch("acloud.create.goldfish_local_image_local_instance.tempfile")
    @mock.patch("acloud.create.goldfish_local_image_local_instance.utils")
    @mock.patch("acloud.create.goldfish_local_image_local_instance."
                "adb_tools.AdbTools")
    @mock.patch("acloud.create.goldfish_local_image_local_instance."
                "subprocess.Popen")
    def testCreateAVDFromSdkRepository(self, mock_popen, mock_adb_tools,
                                       mock_utils, mock_temp_file):
        """Test _CreateAVD with SDK repository files."""
        self._SetUpMocks(mock_popen, mock_adb_tools, mock_utils,
                         mock_temp_file)

        self._CreateEmptyFile(os.path.join(self._image_dir, "system-qemu.img"))
        self._CreateEmptyFile(os.path.join(self._image_dir, "build.prop"))

        mock_environ = {"ANDROID_HOST_OUT": self._temp_dir}

        mock_avd_spec = mock.Mock(local_instance_id=2,
                                  local_image_dir=self._image_dir)

        with mock.patch.dict("acloud.create."
                             "goldfish_local_image_local_instance.os.environ",
                             mock_environ, clear=True):
            self._goldfish._CreateAVD(mock_avd_spec, no_prompts=True)

        instance_dir = os.path.join(self._temp_dir, "acloud_gf_temp",
                                    "instance-2")
        expected_cmd = [
            self._emulator_path, "-verbose", "-show-kernel", "-read-only",
            "-ports", "5556,5557",
            "-logcat-output", os.path.join(instance_dir, "logcat.txt"),
            "-stdouterr-file", os.path.join(instance_dir, "stdouterr.txt")
        ]
        mock_popen.assert_called_once()
        self.assertEqual(mock_popen.call_args[0][0], expected_cmd)
        self._mock_proc.poll.assert_called()

        self.assertTrue(os.path.isfile(
            os.path.join(self._image_dir, "system", "build.prop")))


if __name__ == "__main__":
    unittest.main()
