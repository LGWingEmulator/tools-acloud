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
r"""Instance class.

Define the instance class used to hold details about an AVD instance.

The instance class will hold details about AVD instances (remote/local) used to
enable users to understand what instances they've created. This will be leveraged
for the list, delete, and reconnect commands.

The details include:
- instance name (for remote instances)
- creation date/instance duration
- instance image details (branch/target/build id)
- and more!
"""

import collections
import datetime
import json
import logging
import os
import re
import subprocess
import tempfile

# pylint: disable=import-error
import dateutil.parser
import dateutil.tz

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import utils
from acloud.internal.lib.adb_tools import AdbTools


logger = logging.getLogger(__name__)

_ACLOUD_CVD_TEMP = os.path.join(tempfile.gettempdir(), "acloud_cvd_temp")
_CVD_RUNTIME_FOLDER_NAME = "cuttlefish_runtime"
_LOCAL_INSTANCE_HOME = "instance_home_%s"
_MSG_UNABLE_TO_CALCULATE = "Unable to calculate"
_RE_GROUP_ADB = "local_adb_port"
_RE_GROUP_VNC = "local_vnc_port"
_RE_SSH_TUNNEL_PATTERN = (r"((.*\s*-L\s)(?P<%s>\d+):127.0.0.1:%s)"
                          r"((.*\s*-L\s)(?P<%s>\d+):127.0.0.1:%s)"
                          r"(.+%s)")
_RE_TIMEZONE = re.compile(r"^(?P<time>[0-9\-\.:T]*)(?P<timezone>[+-]\d+:\d+)$")

_COMMAND_PS_LAUNCH_CVD = ["ps", "-wweo", "lstart,cmd"]
_RE_RUN_CVD = re.compile(r"(?P<date_str>^[^/]+)(.*run_cvd)")
_FULL_NAME_STRING = ("device serial: %(device_serial)s (%(instance_name)s) "
                     "elapsed time: %(elapsed_time)s")
LocalPorts = collections.namedtuple("LocalPorts", [constants.VNC_PORT,
                                                   constants.ADB_PORT])


def GetLocalInstanceHomeDir(local_instance_id):
    """Get local instance home dir accroding to instance id.

    Args:
        local_instance_id: Integer of instance id.

    Return:
        String, path of instance home dir.
    """
    return os.path.join(_ACLOUD_CVD_TEMP,
                        _LOCAL_INSTANCE_HOME % local_instance_id)


def GetLocalInstanceRuntimeDir(local_instance_id):
    """Get instance runtime dir

    Args:
        local_instance_id: Integer of instance id.

    Return:
        String, path of instance runtime dir.
    """
    return os.path.join(GetLocalInstanceHomeDir(local_instance_id),
                        _CVD_RUNTIME_FOLDER_NAME)


def GetCuttlefishRuntimeConfig(local_instance_id):
    """Get and parse cuttlefish_config.json.

    Args:
        local_instance_id: Integer of instance id.

    Returns:
        A dictionary that parsed from cuttlefish runtime config.

    Raises:
        errors.ConfigError: if file not found or config load failed.
    """
    runtime_cf_config_path = os.path.join(GetLocalInstanceRuntimeDir(
        local_instance_id), constants.CUTTLEFISH_CONFIG_FILE)
    if not os.path.exists(runtime_cf_config_path):
        raise errors.ConfigError(
            "file does not exist: %s" % runtime_cf_config_path)
    with open(runtime_cf_config_path, "r") as cf_config:
        return json.load(cf_config)


def GetLocalPortsbyInsId(local_instance_id):
    """Get vnc and adb port by local instance id.

    Args:
        local_instance_id: local_instance_id: Integer of instance id.

    Returns:
        NamedTuple of (vnc_port, adb_port) used by local instance, both are
        integers.
    """
    return LocalPorts(vnc_port=constants.CF_VNC_PORT + local_instance_id - 1,
                      adb_port=constants.CF_ADB_PORT + local_instance_id - 1)


def _GetElapsedTime(start_time):
    """Calculate the elapsed time from start_time till now.

    Args:
        start_time: String of instance created time.

    Returns:
        datetime.timedelta of elapsed time, _MSG_UNABLE_TO_CALCULATE for
        datetime can't parse cases.
    """
    match = _RE_TIMEZONE.match(start_time)
    try:
        # Check start_time has timezone or not. If timezone can't be found,
        # use local timezone to get elapsed time.
        if match:
            return datetime.datetime.now(
                dateutil.tz.tzlocal()) - dateutil.parser.parse(start_time)

        return datetime.datetime.now(
            dateutil.tz.tzlocal()) - dateutil.parser.parse(
                start_time).replace(tzinfo=dateutil.tz.tzlocal())
    except ValueError:
        logger.debug(("Can't parse datetime string(%s)."), start_time)
        return _MSG_UNABLE_TO_CALCULATE


class Instance(object):
    """Class to store data of instance."""

    def __init__(self, name, fullname, display, ip, status=None, adb_port=None,
                 vnc_port=None, ssh_tunnel_is_connected=None, createtime=None,
                 elapsed_time=None, avd_type=None, avd_flavor=None,
                 is_local=False, device_information=None):
        self._name = name
        self._fullname = fullname
        self._status = status
        self._display = display  # Resolution and dpi
        self._ip = ip
        self._adb_port = adb_port  # adb port which is forwarding to remote
        self._vnc_port = vnc_port  # vnc port which is forwarding to remote
        # True if ssh tunnel is still connected
        self._ssh_tunnel_is_connected = ssh_tunnel_is_connected
        self._createtime = createtime
        self._elapsed_time = elapsed_time
        self._avd_type = avd_type
        self._avd_flavor = avd_flavor
        self._is_local = is_local  # True if this is a local instance
        self._device_information = device_information

    def __repr__(self):
        """Return full name property for print."""
        return self._fullname

    def Summary(self):
        """Let's make it easy to see what this class is holding."""
        indent = " " * 3
        representation = []
        representation.append(" name: %s" % self._name)
        representation.append("%s IP: %s" % (indent, self._ip))
        representation.append("%s create time: %s" % (indent, self._createtime))
        representation.append("%s elapse time: %s" % (indent, self._elapsed_time))
        representation.append("%s status: %s" % (indent, self._status))
        representation.append("%s avd type: %s" % (indent, self._avd_type))
        representation.append("%s display: %s" % (indent, self._display))
        representation.append("%s vnc: 127.0.0.1:%s" % (indent, self._vnc_port))

        if self._adb_port:
            representation.append("%s adb serial: 127.0.0.1:%s" %
                                  (indent, self._adb_port))
            representation.append("%s product: %s" % (
                indent, self._device_information["product"]))
            representation.append("%s model: %s" % (
                indent, self._device_information["model"]))
            representation.append("%s device: %s" % (
                indent, self._device_information["device"]))
            representation.append("%s transport_id: %s" % (
                indent, self._device_information["transport_id"]))
        else:
            representation.append("%s adb serial: disconnected" % indent)

        return "\n".join(representation)

    @property
    def name(self):
        """Return the instance name."""
        return self._name

    @property
    def fullname(self):
        """Return the instance full name."""
        return self._fullname

    @property
    def ip(self):
        """Return the ip."""
        return self._ip

    @property
    def status(self):
        """Return status."""
        return self._status

    @property
    def display(self):
        """Return display."""
        return self._display

    @property
    def forwarding_adb_port(self):
        """Return the adb port."""
        return self._adb_port

    @property
    def forwarding_vnc_port(self):
        """Return the vnc port."""
        return self._vnc_port

    @property
    def ssh_tunnel_is_connected(self):
        """Return the connect status."""
        return self._ssh_tunnel_is_connected

    @property
    def createtime(self):
        """Return create time."""
        return self._createtime

    @property
    def avd_type(self):
        """Return avd_type."""
        return self._avd_type

    @property
    def avd_flavor(self):
        """Return avd_flavor."""
        return self._avd_flavor

    @property
    def islocal(self):
        """Return if it is a local instance."""
        return self._is_local

    @property
    def adb_port(self):
        """Return adb_port."""
        return self._adb_port

    @property
    def vnc_port(self):
        """Return vnc_port."""
        return self._vnc_port


class LocalInstance(Instance):
    """Class to store data of local instance."""

    def __init__(self, local_instance_id, x_res, y_res, dpi, create_time,
                 ins_dir=None):
        """Initialize a localInstance object.

        Args:
            local_instance_id: Integer of instance id.
            x_res: Integer of x dimension.
            y_res: Integer of y dimension.
            dpi: Integer of dpi.
            date_str: String of create time.
            ins_dir: String, path of instance idr.
        """
        display = ("%sx%s (%s)" % (x_res, y_res, dpi))
        elapsed_time = _GetElapsedTime(create_time) if create_time else None
        name = "%s-%d" % (constants.LOCAL_INS_NAME, local_instance_id)
        local_ports = GetLocalPortsbyInsId(local_instance_id)
        fullname = (_FULL_NAME_STRING %
                    {"device_serial": "127.0.0.1:%d" % local_ports.adb_port,
                     "instance_name": name,
                     "elapsed_time": elapsed_time})
        adb_device = AdbTools(local_ports.adb_port)
        device_information = None
        if adb_device.IsAdbConnected():
            device_information = adb_device.device_information

        super(LocalInstance, self).__init__(
            name=name, fullname=fullname, display=display, ip="127.0.0.1",
            status=constants.INS_STATUS_RUNNING, adb_port=local_ports.adb_port,
            vnc_port=local_ports.vnc_port, createtime=create_time,
            elapsed_time=elapsed_time, avd_type=constants.TYPE_CF,
            is_local=True, device_information=device_information)

        # LocalInstance class properties
        self._instance_dir = ins_dir

    @property
    def instance_dir(self):
        """Return _instance_dir."""
        return self._instance_dir


class RemoteInstance(Instance):
    """Class to store data of remote instance."""

    # pylint: disable=too-many-locals
    def __init__(self, gce_instance):
        """Process the args into class vars.

        RemoteInstace initialized by gce dict object. We parse the required data
        from gce_instance to local variables.
        Reference:
        https://cloud.google.com/compute/docs/reference/rest/v1/instances/get

        We also gather more details on client side including the forwarding adb
        port and vnc port which will be used to determine the status of ssh
        tunnel connection.

        The status of gce instance will be displayed in _fullname property:
        - Connected: If gce instance and ssh tunnel and adb connection are all
         active.
        - No connected: If ssh tunnel or adb connection is not found.
        - Terminated: If we can't retrieve the public ip from gce instance.

        Args:
            gce_instance: dict object queried from gce.
        """
        name = gce_instance.get(constants.INS_KEY_NAME)

        create_time = gce_instance.get(constants.INS_KEY_CREATETIME)
        elapsed_time = _GetElapsedTime(create_time)
        status = gce_instance.get(constants.INS_KEY_STATUS)

        ip = None
        for network_interface in gce_instance.get("networkInterfaces"):
            for access_config in network_interface.get("accessConfigs"):
                ip = access_config.get("natIP")

        # Get metadata
        display = None
        avd_type = None
        avd_flavor = None
        for metadata in gce_instance.get("metadata", {}).get("items", []):
            key = metadata["key"]
            value = metadata["value"]
            if key == constants.INS_KEY_DISPLAY:
                display = value
            elif key == constants.INS_KEY_AVD_TYPE:
                avd_type = value
            elif key == constants.INS_KEY_AVD_FLAVOR:
                avd_flavor = value

        # Find ssl tunnel info.
        adb_port = None
        vnc_port = None
        device_information = None
        if ip:
            forwarded_ports = self.GetAdbVncPortFromSSHTunnel(ip, avd_type)
            adb_port = forwarded_ports.adb_port
            vnc_port = forwarded_ports.vnc_port
            ssh_tunnel_is_connected = adb_port is not None

            adb_device = AdbTools(adb_port)
            if adb_device.IsAdbConnected():
                device_information = adb_device.device_information
                fullname = (_FULL_NAME_STRING %
                            {"device_serial": "127.0.0.1:%d" % adb_port,
                             "instance_name": name,
                             "elapsed_time": elapsed_time})
            else:
                fullname = (_FULL_NAME_STRING %
                            {"device_serial": "not connected",
                             "instance_name": name,
                             "elapsed_time": elapsed_time})
        # If instance is terminated, its ip is None.
        else:
            ssh_tunnel_is_connected = False
            fullname = (_FULL_NAME_STRING %
                        {"device_serial": "terminated",
                         "instance_name": name,
                         "elapsed_time": elapsed_time})

        super(RemoteInstance, self).__init__(
            name=name, fullname=fullname, display=display, ip=ip, status=status,
            adb_port=adb_port, vnc_port=vnc_port,
            ssh_tunnel_is_connected=ssh_tunnel_is_connected,
            createtime=create_time, elapsed_time=elapsed_time, avd_type=avd_type,
            avd_flavor=avd_flavor, is_local=False,
            device_information=device_information)

    @staticmethod
    def GetAdbVncPortFromSSHTunnel(ip, avd_type):
        """Get forwarding adb and vnc port from ssh tunnel.

        Args:
            ip: String, ip address.
            avd_type: String, the AVD type.

        Returns:
            NamedTuple ForwardedPorts(vnc_port, adb_port) holding the ports
            used in the ssh forwarded call. Both fields are integers.
        """
        if avd_type not in utils.AVD_PORT_DICT:
            return utils.ForwardedPorts(vnc_port=None, adb_port=None)

        default_vnc_port = utils.AVD_PORT_DICT[avd_type].vnc_port
        default_adb_port = utils.AVD_PORT_DICT[avd_type].adb_port
        re_pattern = re.compile(_RE_SSH_TUNNEL_PATTERN %
                                (_RE_GROUP_VNC, default_vnc_port,
                                 _RE_GROUP_ADB, default_adb_port, ip))
        adb_port = None
        vnc_port = None
        process_output = subprocess.check_output(constants.COMMAND_PS)
        for line in process_output.splitlines():
            match = re_pattern.match(line)
            if match:
                adb_port = int(match.group(_RE_GROUP_ADB))
                vnc_port = int(match.group(_RE_GROUP_VNC))
                break

        logger.debug(("grathering detail for ssh tunnel. "
                      "IP:%s, forwarding (adb:%d, vnc:%d)"), ip, adb_port,
                     vnc_port)

        return utils.ForwardedPorts(vnc_port=vnc_port, adb_port=adb_port)
