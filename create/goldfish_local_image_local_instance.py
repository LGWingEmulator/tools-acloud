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
r"""GoldfishLocalImageLocalInstance class.

Create class that is responsible for creating a  local goldfish instance with
local images.

The emulator binary supports two types of environments, Android build system
and SDK. This class runs emulator in the build environment.
- In a real build environment, this class uses the prebuilt emulator in
  ANDROID_EMULATOR_PREBUILTS.
- If this program is not in a build environment, the user must set
  ANDROID_HOST_OUT to an unzipped SDK repository, i.e.,
  sdk-repo-<os>-emulator-<build>.zip
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile

from acloud import errors
from acloud.create import base_avd_create
from acloud.internal import constants
from acloud.internal.lib import adb_tools
from acloud.internal.lib import utils
from acloud.public import report


logger = logging.getLogger(__name__)

_EMULATOR_BIN_NAME = "emulator"
_SDK_REPO_EMULATOR_DIR_NAME = "emulator"
_GF_ADB_DEVICE_SERIAL = "emulator-%(console_port)s"
_EMULATOR_DEFAULT_CONSOLE_PORT = 5554
_EMULATOR_TIMEOUT_SECS = 150
_EMULATOR_TIMEOUT_ERROR = ("Emulator did not boot within %d secs." %
                           _EMULATOR_TIMEOUT_SECS)
_EMU_KILL_TIMEOUT_SECS = 20
_EMU_KILL_TIMEOUT_ERROR = ("Emulator did not stop within %d secs." %
                           _EMU_KILL_TIMEOUT_SECS)
_CONFIRM_RELAUNCH = ("\nGoldfish AVD is already running. \n"
                     "Enter 'y' to terminate current instance and launch a "
                     "new instance, enter anything else to exit out[y/N]: ")


class GoldfishLocalImageLocalInstance(base_avd_create.BaseAVDCreate):
    """Create class for a local image local instance emulator."""

    def _CreateAVD(self, avd_spec, no_prompts):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that provides the local image directory.
            no_prompts: Boolean, True to skip all prompts.

        Returns:
            A Report instance.

        Raises:
            errors.GetSdkRepoPackageError if emulator binary is not found.
            errors.GetLocalImageError if the local image directory does not
            contain required files.
            errors.CreateError if an instance exists and cannot be deleted.
            errors.DeviceBootTimeoutError if the emulator does not boot within
            timeout.
            errors.EmulatorFail if the emulator process terminates.
        """
        if not utils.IsSupportedPlatform(print_warning=True):
            result_report = report.Report(constants.LOCAL_INS_NAME)
            result_report.SetStatus(report.Status.FAIL)
            return result_report

        emulator_path = self._FindEmulatorBinary()
        if not emulator_path or not os.path.isfile(emulator_path):
            raise errors.GetSdkRepoPackageError("Cannot find emulator binary.")
        emulator_path = os.path.abspath(emulator_path)

        image_dir = os.path.abspath(avd_spec.local_image_dir)

        if not (os.path.isfile(os.path.join(image_dir, "system.img")) or
                os.path.isfile(os.path.join(image_dir, "system-qemu.img"))):
            raise errors.GetLocalImageError("No system image in %s." %
                                            image_dir)

        # TODO(b/141898893): In Android build environment, emulator gets build
        # information from $ANDROID_PRODUCT_OUT/system/build.prop.
        # If image_dir is an extacted SDK repository, the file is at
        # image_dir/build.prop. Acloud copies it to
        # image_dir/system/build.prop.
        build_porp_path = os.path.join(image_dir, "system", "build.prop")
        if not os.path.exists(build_porp_path):
            build_prop_src_path = os.path.join(image_dir, "build.prop")
            if not os.path.isfile(build_prop_src_path):
                raise errors.GetLocalImageError("No build.prop in %s." %
                                                image_dir)
            build_porp_dir = os.path.dirname(build_porp_path)
            logger.info("Copy build.prop to %s", build_porp_path)
            if not os.path.exists(build_porp_dir):
                os.makedirs(build_porp_dir)
            shutil.copyfile(build_prop_src_path, build_porp_path)

        console_port = _EMULATOR_DEFAULT_CONSOLE_PORT
        adb_port = constants.GF_ADB_PORT
        adb = adb_tools.AdbTools(
            adb_port=adb_port,
            device_serial=_GF_ADB_DEVICE_SERIAL % {
                "console_port": console_port})

        self._CheckRunningEmulator(adb, no_prompts)

        instance_dir = os.path.join(tempfile.gettempdir(), "acloud_gf_temp")
        shutil.rmtree(instance_dir, ignore_errors=True)
        os.mkdir(instance_dir)

        logger.info("Instance directory: %s", instance_dir)
        proc = self._StartEmulatorProcess(emulator_path, instance_dir,
                                          image_dir, console_port, adb_port)

        self._WaitForEmulatorToStart(adb, proc)

        result_report = report.Report(command="create")
        result_report.SetStatus(report.Status.SUCCESS)
        # Emulator has no VNC port.
        result_report.AddData(
            key="devices",
            value={constants.ADB_PORT: adb_port})
        return result_report

    @staticmethod
    def _FindEmulatorBinary():
        """Return the path to the emulator binary in build environment."""
        # This program is running in build environment.
        prebuilt_emulator_dir = os.environ.get(
            constants.ENV_ANDROID_EMULATOR_PREBUILTS)
        if prebuilt_emulator_dir:
            return os.path.join(prebuilt_emulator_dir, _EMULATOR_BIN_NAME)

        # Assume sdk-repo-*.zip is extracted to ANDROID_HOST_OUT.
        sdk_repo_dir = os.environ.get(constants.ENV_ANDROID_HOST_OUT)
        if sdk_repo_dir:
            return os.path.join(sdk_repo_dir, _SDK_REPO_EMULATOR_DIR_NAME,
                                _EMULATOR_BIN_NAME)

        return None

    @staticmethod
    def _IsEmulatorRunning(adb):
        """Check existence of an emulator by sending an empty command.

        Args:
            adb: adb_tools.AdbTools initialized with the emulator's serial.

        Returns:
            Boolean, whether the emulator is running.
        """
        return adb.EmuCommand() == 0

    def _CheckRunningEmulator(self, adb, no_prompts):
        """Attempt to delete a running emulator.

        Args:
            adb: adb_tools.AdbTools initialized with the emulator's serial.
            no_prompts: Boolean, True to skip all prompts.

        Raises:
            errors.CreateError if the emulator isn't deleted.
        """
        if not self._IsEmulatorRunning(adb):
            return
        logger.info("Goldfish AVD is already running.")
        if no_prompts or utils.GetUserAnswerYes(_CONFIRM_RELAUNCH):
            if adb.EmuCommand("kill") != 0:
                raise errors.CreateError("Cannot kill emulator.")
            self._WaitForEmulatorToStop(adb)
        else:
            sys.exit(constants.EXIT_BY_USER)

    @staticmethod
    def _StartEmulatorProcess(emulator_path, working_dir, image_dir,
                              console_port, adb_port):
        """Start an emulator process.

        Args:
            emulator_path: The path to emulator binary.
            working_dir: The working directory for the emulator process.
                         The emulator command creates files in the directory.
            image_dir: The directory containing the required images.
                       e.g., composite system.img or system-qemu.img.
            console_port: The console port of the emulator.
            adb_port: The ADB port of the emulator.

        Returns:
            A Popen object, the emulator process.
        """
        emulator_env = os.environ.copy()
        emulator_env[constants.ENV_ANDROID_PRODUCT_OUT] = image_dir
        # Set ANDROID_BUILD_TOP so that the emulator considers itself to be in
        # build environment.
        if constants.ENV_ANDROID_BUILD_TOP not in emulator_env:
            emulator_env[constants.ENV_ANDROID_BUILD_TOP] = image_dir

        logcat_path = os.path.join(working_dir, "logcat.txt")
        stdouterr_path = os.path.join(working_dir, "stdouterr.txt")
        # The command doesn't create -stdouterr-file automatically.
        with open(stdouterr_path, "w") as _:
            pass

        emulator_cmd = [
            os.path.abspath(emulator_path), "-verbose", "-show-kernel",
            "-ports", str(console_port) + "," + str(adb_port),
            "-logcat-output", logcat_path,
            "-stdouterr-file", stdouterr_path
        ]

        with open(os.devnull, "rb+") as devnull:
            return subprocess.Popen(
                emulator_cmd, shell=False, cwd=working_dir, env=emulator_env,
                stdin=devnull, stdout=devnull, stderr=devnull)

    def _WaitForEmulatorToStop(self, adb):
        """Wait for an emulator to be unavailable on the console port.

        Args:
            adb: adb_tools.AdbTools initialized with the emulator's serial.

        Raises:
            errors.CreateError if the emulator does not stop within timeout.
        """
        create_error = errors.CreateError(_EMU_KILL_TIMEOUT_ERROR)
        utils.PollAndWait(func=lambda: self._IsEmulatorRunning(adb),
                          expected_return=False,
                          timeout_exception=create_error,
                          timeout_secs=_EMU_KILL_TIMEOUT_SECS,
                          sleep_interval_secs=1)

    def _WaitForEmulatorToStart(self, adb, proc):
        """Wait for an emulator to be available on the console port.

        Args:
            adb: adb_tools.AdbTools initialized with the emulator's serial.
            proc: Popen object, the running emulator process.

        Raises:
            errors.DeviceBootTimeoutError if the emulator does not boot within
            timeout.
            errors.EmulatorFail if the process terminates.
        """
        timeout_error = errors.DeviceBootTimeoutError(_EMULATOR_TIMEOUT_ERROR)
        utils.PollAndWait(func=lambda: (proc.poll() is None and
                                        self._IsEmulatorRunning(adb)),
                          expected_return=True,
                          timeout_exception=timeout_error,
                          timeout_secs=_EMULATOR_TIMEOUT_SECS,
                          sleep_interval_secs=5)
        if proc.poll() is not None:
            raise errors.EmulatorFail("Emulator process returned %d." %
                                      proc.returncode)
