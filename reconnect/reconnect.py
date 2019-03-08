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

from collections import namedtuple
import getpass
import re

from acloud.delete import delete
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.internal.lib.adb_tools import AdbTools
from acloud.list import list as list_instance
from acloud.public import config

_RE_DISPLAY = re.compile(r"([\d]+)x([\d]+)\s.*")
_VNC_STARTED_PATTERN = "ssvnc vnc://127.0.0.1:%(vnc_port)d"
# TODO(b/122929848): merge all definition of ForwardedPorts into one spot.
ForwardedPorts = namedtuple("ForwardedPorts",
                            [constants.VNC_PORT, constants.ADB_PORT])
_AVD_PORT_CLASS_DICT = {
    constants.TYPE_GCE: ForwardedPorts(constants.DEFAULT_GCE_VNC_PORT,
                                       constants.DEFAULT_GCE_ADB_PORT),
    constants.TYPE_CF: ForwardedPorts(constants.CF_TARGET_VNC_PORT,
                                      constants.CF_TARGET_ADB_PORT)
}


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
        delete.CleanupSSVncviewer(vnc_port)

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
        forwarded_ports = utils.AutoConnect(
            instance.ip,
            ssh_private_key_path,
            _AVD_PORT_CLASS_DICT.get(instance.avd_type).vnc_port,
            _AVD_PORT_CLASS_DICT.get(instance.avd_type).adb_port,
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
