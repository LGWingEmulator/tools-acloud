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
"""A tool that help to run adb to check device status."""

from distutils.spawn import find_executable

import re
import subprocess

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import utils

_ADB_CONNECT = "connect"
_ADB_DEVICE = "devices"
_ADB_DISCONNECT = "disconnect"
_ADB_STATUS_DEVICE = "device"
_ADB_STATUS_DEVICE_ARGS = "-l"
_RE_ADB_DEVICE_INFO = (r"%s\s*(?P<adb_status>[\S]+)? ?"
                       r"(usb:(?P<usb>[\S]+))? ?"
                       r"(product:(?P<product>[\S]+))? ?"
                       r"(model:(?P<model>[\S]+))? ?"
                       r"(device:(?P<device>[\S]+))? ?"
                       r"(transport_id:(?P<transport_id>[\S]+))? ?")
_DEVICE_ATTRIBUTES = ["adb_status", "usb", "product", "model", "device", "transport_id"]
#KEY_CODE 82 = KEY_MENU
_UNLOCK_SCREEN_KEYEVENT = ("%(adb_bin)s -s %(device_serial)s "
                           "shell input keyevent 82")


class AdbTools(object):
    """Adb tools.

    Attributes:
        _adb_command: String, combine adb commands then execute it.
        _adb_port: Integer, Specified adb port to establish connection.
        _device_serial: String, adb devices serial.
        _device_information: Dict, will be added to adb information include usb,
                            product model, device and transport_id
    """
    def __init__(self, adb_port=None):
        """Initialize.

        Args:
            adb_port: String of adb port number.
        """
        self._adb_command = ""
        self._adb_port = adb_port
        self._device_serial = ""
        self._device_information = {}
        self._SetDeviceSerial()
        self._CheckAdb()
        self._GetAdbInformation()

    def _SetDeviceSerial(self):
        """Set device serial."""
        if self._adb_port:
            self._device_serial = "127.0.0.1:%s" % self._adb_port

    def _CheckAdb(self):
        """Find adb bin path.

        Raises:
            errors.NoExecuteCmd: Can't find the execute adb bin.
        """
        self._adb_command = find_executable(constants.ADB_BIN)
        if not self._adb_command:
            raise errors.NoExecuteCmd("Can't find the adb command.")

    def GetAdbConnectionStatus(self):
        """Get Adb connect status.

        Check if self._adb_port is null (ssh tunnel is broken).

        Returns:
            String, the result of adb connection.
        """
        if not self._adb_port:
            return None

        return self._device_information["adb_status"]

    def _GetAdbInformation(self):
        """Get Adb connect information.

        1. Check adb devices command to get the connection information.

        2. Gather information include usb, product model, device and transport_id
        when the attached field is device.

        e.g.
            Case 1:
            List of devices attached
            127.0.0.1:48451 device product:aosp_cf model:Cuttlefish device:vsoc_x86 transport_id:147
            _device_information = {"adb_status":"device",
                                   "usb":None,
                                   "product":"aosp_cf",
                                   "model":"Cuttlefish",
                                   "device":"vsoc_x86",
                                   "transport_id":"147"}

            Case 2:
            List of devices attached
            127.0.0.1:48451 offline
            _device_information = {"adb_status":"offline",
                                   "usb":None,
                                   "product":None,
                                   "model":None,
                                   "device":None,
                                   "transport_id":None}

            Case 3:
            List of devices attached
            _device_information = {"adb_status":None,
                                   "usb":None,
                                   "product":None,
                                   "model":None,
                                   "device":None,
                                   "transport_id":None}
        """
        adb_cmd = [self._adb_command, _ADB_DEVICE, _ADB_STATUS_DEVICE_ARGS]
        device_info = subprocess.check_output(adb_cmd)
        self._device_information = {
            attribute: None for attribute in _DEVICE_ATTRIBUTES}

        for device in device_info.splitlines():
            match = re.match(_RE_ADB_DEVICE_INFO % self._device_serial, device)
            if match:
                self._device_information = {
                    attribute: match.group(attribute) if match.group(attribute)
                               else None for attribute in _DEVICE_ATTRIBUTES}

    def IsAdbConnectionAlive(self):
        """Check devices connect alive.

        Returns:
            Boolean, True if adb status is device. False otherwise.
        """
        return self.GetAdbConnectionStatus() == _ADB_STATUS_DEVICE

    def IsAdbConnected(self):
        """Check devices connected or not.

        If adb connected and the status is device or offline, return True.
        If there is no any connection, return False.

        Returns:
            Boolean, True if adb status not none. False otherwise.
        """
        return self.GetAdbConnectionStatus() is not None

    def DisconnectAdb(self):
        """Disconnect adb.

        Only disconnect if the devices shows up in adb devices.
        """
        try:
            if self.IsAdbConnected():
                adb_disconnect_args = [self._adb_command,
                                       _ADB_DISCONNECT,
                                       self._device_serial]
                subprocess.check_call(adb_disconnect_args)
        except subprocess.CalledProcessError:
            utils.PrintColorString("Failed to adb disconnect %s" %
                                   self._device_serial,
                                   utils.TextColors.FAIL)

    def ConnectAdb(self):
        """Connect adb.

        Only connect if adb connection is not alive.
        """
        try:
            if not self.IsAdbConnectionAlive():
                adb_connect_args = [self._adb_command,
                                    _ADB_CONNECT,
                                    self._device_serial]
                subprocess.check_call(adb_connect_args)
        except subprocess.CalledProcessError:
            utils.PrintColorString("Failed to adb connect %s" %
                                   self._device_serial,
                                   utils.TextColors.FAIL)

    def AutoUnlockScreen(self):
        """Auto unlock screen.

        Auto unlock screen after invoke vnc client.
        """
        try:
            adb_unlock_args = _UNLOCK_SCREEN_KEYEVENT % {
                "adb_bin": self._adb_command,
                "device_serial": self._device_serial}
            subprocess.check_call(adb_unlock_args.split())
        except subprocess.CalledProcessError:
            utils.PrintColorString("Failed to unlock screen."
                                   "(adb_port: %s)" % self._adb_port,
                                   utils.TextColors.WARNING)

    @property
    def device_information(self):
        """Return the device information."""
        return self._device_information
