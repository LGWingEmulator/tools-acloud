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

"""Action to create goldfish device instances.

A Goldfish device is an emulated android device based on the android
emulator.
"""
import logging
import os

from acloud.public.actions import common_operations
from acloud.public.actions import base_device_factory
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.internal.lib import goldfish_compute_client

logger = logging.getLogger(__name__)

ALL_SCOPES = " ".join([
    android_build_client.AndroidBuildClient.SCOPE,
    goldfish_compute_client.GoldfishComputeClient.SCOPE
])


class GoldfishDeviceFactory(base_device_factory.BaseDeviceFactory):
  """A class that can produce a goldfish device."""

  def __init__(self,
               cfg,
               build_target,
               build_id,
               emulator_build_target,
               emulator_build_id,
               gpu=None):
    self.credentials = auth.CreateCredentials(cfg, ALL_SCOPES)

    compute_client = goldfish_compute_client.GoldfishComputeClient(
        cfg, self.credentials)
    super(GoldfishDeviceFactory, self).__init__(compute_client)

    # Private creation parameters
    self._cfg = cfg
    self._build_target = build_target
    self._build_id = build_id
    self._emulator_build_id = emulator_build_id
    self._emulator_build_target = emulator_build_target
    self._gpu = gpu
    self._blank_data_disk_size_gb = cfg.extra_data_disk_size_gb

    # Configure clients
    self._build_client = android_build_client.AndroidBuildClient(
        self.credentials)

    # Discover branches
    self._branch = self._build_client.GetBranch(build_target, build_id)
    self._emulator_branch = self._build_client.GetBranch(
        emulator_build_target, emulator_build_id)

  def CreateInstance(self):
    """Creates singe configured goldfish device.

    Override method from parent class.

    Returns:
      The name of the created instance.
    """
    instance = self._compute_client.GenerateInstanceName(self._build_id)

    self._compute_client.CreateInstance(
        instance=instance,
        image_name=self._cfg.stable_goldfish_host_image_name,
        image_project=self._cfg.stable_goldfish_host_image_project,
        build_target=self._build_target,
        branch=self._branch,
        build_id=self._build_id,
        emulator_branch=self._emulator_branch,
        emulator_build_id=self._emulator_build_id,
        gpu=self._gpu,
        blank_data_disk_size_gb=self._blank_data_disk_size_gb)

    return instance


def CreateDevices(cfg,
                  build_target=None,
                  build_id=None,
                  emulator_build_id=None,
                  gpu=None,
                  num=1,
                  serial_log_file=None,
                  logcat_file=None,
                  autoconnect=False):
  """Create one or multiple Goldfish devices.

  Args:
    cfg: An AcloudConfig instance.
    build_target: Target name.
    build_id: Build id, a string, e.g. "2263051", "P2804227"
    emulator_build_id: emulator build id, a string.
    gpu: GPU to attach to the device or None. e.g. "nvidia-tesla-k80"
    num: Number of devices to create.
    serial_log_file: A path to a file where serial output should
                        be saved to.
    logcat_file: A path to a file where logcat logs should be saved.
    autoconnect: Create ssh tunnel(s) and adb connect after device creation.

  Returns:
    A Report instance.
  """
  # TODO(fdeng, pinghao): Implement copying files from the instance, including
  # the serial log (kernel log), and logcat log files.
  # TODO(fdeng, pinghao): Implement autoconnect.
  logger.info("Creating a goldfish device in project %s, build_target: %s, "
              "build_id: %s, emulator_bid: %s, GPU: %s, num: %s, "
              "serial_log_file: %s, logcat_file: %s, "
              "autoconnect: %s", cfg.project, build_target, build_id,
              emulator_build_id, gpu, num, serial_log_file, logcat_file,
              autoconnect)

  device_factory = GoldfishDeviceFactory(cfg, build_target, build_id,
                                         cfg.emulator_build_target,
                                         emulator_build_id, gpu)

  return common_operations.CreateDevices("create_gf", cfg, device_factory, num)
