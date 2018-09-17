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
"""Common operations between managing GCE and Cuttlefish devices.

This module provides the common operations between managing GCE (device_driver)
and Cuttlefish (create_cuttlefish_action) devices. Should not be called
directly.
"""

from __future__ import print_function
import logging

from acloud.public import avd
from acloud.public import errors
from acloud.public import report
from acloud.internal.lib import utils

logger = logging.getLogger(__name__)


def CreateSshKeyPairIfNecessary(cfg):
    """Create ssh key pair if necessary.

    Args:
        cfg: An Acloudconfig instance.

    Raises:
        error.DriverError: If it falls into an unexpected condition.
    """
    if not cfg.ssh_public_key_path:
        logger.warning(
            "ssh_public_key_path is not specified in acloud config. "
            "Project-wide public key will "
            "be used when creating AVD instances. "
            "Please ensure you have the correct private half of "
            "a project-wide public key if you want to ssh into the "
            "instances after creation.")
    elif cfg.ssh_public_key_path and not cfg.ssh_private_key_path:
        logger.warning(
            "Only ssh_public_key_path is specified in acloud config, "
            "but ssh_private_key_path is missing. "
            "Please ensure you have the correct private half "
            "if you want to ssh into the instances after creation.")
    elif cfg.ssh_public_key_path and cfg.ssh_private_key_path:
        utils.CreateSshKeyPairIfNotExist(cfg.ssh_private_key_path,
                                         cfg.ssh_public_key_path)
    else:
        # Should never reach here.
        raise errors.DriverError(
            "Unexpected error in CreateSshKeyPairIfNecessary")


class DevicePool(object):
    """A class that manages a pool of virtual devices.

    Attributes:
        devices: A list of devices in the pool.
    """

    def __init__(self, device_factory, devices=None):
        """Constructs a new DevicePool.

        Args:
            device_factory: A device factory capable of producing a goldfish or
                cuttlefish device. The device factory must expose an attribute with
                the credentials that can be used to retrieve information from the
                constructed device.
            devices: List of devices managed by this pool.
        """
        self._devices = devices or []
        self._device_factory = device_factory
        self._compute_client = device_factory.GetComputeClient()

    def CreateDevices(self, num):
        """Creates |num| devices for given build_target and build_id.

        Args:
            num: Number of devices to create.
        """

        # Create host instances for cuttlefish/goldfish device.
        # Currently one instance supports only 1 device.
        for _ in range(num):
            instance = self._device_factory.CreateInstance()
            ip = self._compute_client.GetInstanceIP(instance)
            self.devices.append(
                avd.AndroidVirtualDevice(ip=ip, instance_name=instance))

    @utils.TimeExecute(function_description="Waiting for AVD(s) to boot up")
    def WaitForBoot(self):
        """Waits for all devices to boot up.

        Returns:
            A dictionary that contains all the failures.
            The key is the name of the instance that fails to boot,
            and the value is an errors.DeviceBootError object.
        """
        failures = {}
        for device in self._devices:
            try:
                self._compute_client.WaitForBoot(device.instance_name)
            except errors.DeviceBootError as e:
                failures[device.instance_name] = e
        return failures

    @property
    def devices(self):
        """Returns a list of devices in the pool.

        Returns:
            A list of devices in the pool.
        """
        return self._devices


def CreateDevices(command, cfg, device_factory, num, report_internal_ip=False):
    """Create a set of devices using the given factory.

    Main jobs in create devices.
        1. Create GCE instance: Launch instance in GCP(Google Cloud Platform).
        2. Starting up AVD: Wait device boot up.

    Args:
        command: The name of the command, used for reporting.
        cfg: An AcloudConfig instance.
        device_factory: A factory capable of producing a single device.
        num: The number of devices to create.
        report_internal_ip: Boolean to report the internal ip instead of
                            external ip.

    Raises:
        errors: Create instance fail.

    Returns:
        A Report instance.
    """
    reporter = report.Report(command=command)
    try:
        CreateSshKeyPairIfNecessary(cfg)
        device_pool = DevicePool(device_factory)
        device_pool.CreateDevices(num)
        failures = device_pool.WaitForBoot()
        if failures:
            reporter.SetStatus(report.Status.BOOT_FAIL)
        else:
            reporter.SetStatus(report.Status.SUCCESS)
        # Write result to report.
        for device in device_pool.devices:
            device_dict = {
                "ip": (device.ip.internal if report_internal_ip
                       else device.ip.external),
                "instance_name": device.instance_name
            }
            if device.instance_name in failures:
                reporter.AddData(key="devices_failing_boot", value=device_dict)
                reporter.AddError(str(failures[device.instance_name]))
            else:
                reporter.AddData(key="devices", value=device_dict)
    except errors.DriverError as e:
        reporter.AddError(str(e))
        reporter.SetStatus(report.Status.FAIL)
    return reporter
