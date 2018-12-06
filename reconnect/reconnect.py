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
r"""Reconnect entry point.

Reconnect will:
 - re-establish ssh tunnels for adb/vnc port forwarding for a remote instance
 - adb connect to forwarded ssh port for remote instance
 - restart vnc for remote/local instances
"""

from __future__ import print_function
from distutils.spawn import find_executable
import getpass
import re
import subprocess

from acloud import errors as root_errors
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.list import list as list_instance
from acloud.public import config

_ADB_CONNECT = "connect"
_ADB_DEVICE = "devices"
_ADB_DISCONNECT = "disconnect"
_ADB_STATUS_DEVICE = "device"
_COMMAND_KILLVNC = ["pkill", "-9", "-f"]
_RE_DISPLAY = re.compile(r"([\d]+)x([\d]+)\s.*")
_SSVNC_VIEWER_PATTERN = "vnc://127.0.0.1:%(vnc_port)d"
_VNC_STARTED_PATTERN = "ssvnc vnc://127.0.0.1:%(vnc_port)d"


class AdbTools(object):
    """Adb tools.

    Args:
        adb_port: String of adb port number.
    """
    def __init__(self, adb_port=None):
        self._adb_command = ""
        self._adb_port = adb_port
        self._device_serial = ""
        self._SetDeviceSerial()
        self._CheckAdb()

    def _SetDeviceSerial(self):
        """Set device serial."""
        if self._adb_port:
            self._device_serial = "127.0.0.1:%s" % self._adb_port

    def _CheckAdb(self):
        """Find adb bin path.

        Raises:
            root_errors.NoExecuteCmd: Can't find the execute adb bin.
        """
        self._adb_command = find_executable(constants.ADB_BIN)
        if not self._adb_command:
            raise root_errors.NoExecuteCmd("Can't find the adb command.")

    def GetAdbConnectionStatus(self):
        """Get Adb connect status.

        Users uses adb devices command to get the connection status of the
        adb devices. When the attached field is device, then device is returned,
        if it is offline, then offline is returned. If no device is found,
        the None is returned.

        e.g.
            Case 1: return device
            List of devices attached
            127.0.0.1:48451 device

            Case 2: return offline
            List of devices attached
            127.0.0.1:48451 offline

            Case 3: return None
            List of devices attached

        Returns:
            String, the result of adb connection.
        """
        adb_cmd = [self._adb_command, _ADB_DEVICE]
        device_info = subprocess.check_output(adb_cmd)
        for device in device_info.splitlines():
            match = re.match(r"%s\s(?P<adb_status>.+)" % self._device_serial, device)
            if match:
                return match.group("adb_status")
        return None

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


def CleanupSSVncviewer(ssvnc_viewer_pattern):
    """Cleanup the old disconnected ssvnc viewer.

    Args:
        ssvnc_viewer_pattern: String, ssvnc viewer pattern.
    """
    if utils.IsCommandRunning(ssvnc_viewer_pattern):
        command_kill_vnc = _COMMAND_KILLVNC + [ssvnc_viewer_pattern]
        subprocess.check_call(command_kill_vnc)


def StartVnc(vnc_port, display):
    """Start vnc connect to AVD.

    Confirm whether there is already a connection before VNC connection.
    If there is a connection, it will not be connected. If not, connect it.
    Before reconnecting, clear old disconnect ssvnc viewer.

    Args:
        vnc_port: Integer of vnc port number.
        display: String, vnc connection resolution. e.g., 1080x720 (240)
    """
    vnc_started_pattern = _VNC_STARTED_PATTERN % {"vnc_port": vnc_port}
    if not utils.IsCommandRunning(vnc_started_pattern):
        #clean old disconnect ssvnc viewer.
        ssvnc_viewer_pattern = _SSVNC_VIEWER_PATTERN % {"vnc_port": vnc_port}
        CleanupSSVncviewer(ssvnc_viewer_pattern)

        match = _RE_DISPLAY.match(display)
        if match:
            utils.LaunchVncClient(vnc_port, match.group(1), match.group(2))
        else:
            utils.LaunchVncClient(vnc_port)


def ReconnectInstance(ssh_private_key_path, instance):
    """Reconnect adb/vnc/ssh to the specified instance.

    Args:
        ssh_private_key_path: Path to the private key file.
                              e.g. ~/.ssh/acloud_rsa
        instance: list.Instance() object.
    """
    adb_cmd = AdbTools(instance.forwarding_adb_port)
    vnc_port = instance.forwarding_vnc_port
    # ssh tunnel is up but device is disconnected on adb
    if instance.ssh_tunnel_is_connected and not adb_cmd.IsAdbConnectionAlive():
        adb_cmd.DisconnectAdb()
        adb_cmd.ConnectAdb()
    # ssh tunnel is down and it's a remote instance
    elif not instance.ssh_tunnel_is_connected and not instance.islocal:
        adb_cmd.DisconnectAdb()
        forwarded_ports = utils.AutoConnect(instance.ip,
                                            ssh_private_key_path,
                                            constants.CF_TARGET_VNC_PORT,
                                            constants.CF_TARGET_ADB_PORT,
                                            getpass.getuser())
        vnc_port = forwarded_ports.vnc_port

    if vnc_port:
        StartVnc(vnc_port, instance.display)


def Run(args):
    """Run reconnect.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    cfg = config.GetAcloudConfig(args)
    instances_to_reconnect = []
    if args.instance_names is not None:
        # user input instance name to get instance object.
        instances_to_reconnect = list_instance.GetInstancesFromInstanceNames(
            cfg, args.instance_names)
    if not instances_to_reconnect:
        instances_to_reconnect = list_instance.ChooseInstances(cfg, args.all)
    for instance in instances_to_reconnect:
        ReconnectInstance(cfg.ssh_private_key_path, instance)
