# Copyright 2020 - The Android Open Source Project
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
"""cvd_runtime_config class."""

import json
import os

from acloud import errors

_CFG_KEY_ADB_CONNECTOR_BINARY = "adb_connector_binary"
_CFG_KEY_X_RES = "x_res"
_CFG_KEY_Y_RES = "y_res"
_CFG_KEY_DPI = "dpi"
_CFG_KEY_ADB_IP_PORT = "adb_ip_and_port"
_CFG_KEY_INSTANCE_DIR = "instance_dir"
_CFG_KEY_VNC_PORT = "vnc_server_port"
_CFG_KEY_ADB_PORT = "host_port"


class CvdRuntimeConfig(object):
    """The class that hold the information from cuttlefish_config.json."""

    def __init__(self, config_path):
        self._config_dict = self._GetCuttlefishRuntimeConfig(config_path)
        self._x_res = self._config_dict.get(_CFG_KEY_X_RES)
        self._y_res = self._config_dict.get(_CFG_KEY_Y_RES)
        self._dpi = self._config_dict.get(_CFG_KEY_DPI)
        self._instance_dir = self._config_dict.get(_CFG_KEY_INSTANCE_DIR)
        self._vnc_port = self._config_dict.get(_CFG_KEY_VNC_PORT)
        self._adb_port = self._config_dict.get(_CFG_KEY_ADB_PORT)
        self._adb_ip_port = self._config_dict.get(_CFG_KEY_ADB_IP_PORT)

        adb_connector = self._config_dict.get(_CFG_KEY_ADB_CONNECTOR_BINARY)
        self._cvd_tools_path = (os.path.dirname(adb_connector)
                                if adb_connector else None)

    @staticmethod
    def _GetCuttlefishRuntimeConfig(runtime_cf_config_path):
        """Get and parse cuttlefish_config.json.

        Args:
            runtime_cf_config_path: String, path of the cvd runtime config.

        Returns:
            A dictionary that parsed from cuttlefish runtime config.

        Raises:
            errors.ConfigError: if file not found or config load failed.
        """
        if not os.path.exists(runtime_cf_config_path):
            raise errors.ConfigError(
                "file does not exist: %s" % runtime_cf_config_path)
        with open(runtime_cf_config_path, "r") as cf_config:
            return json.load(cf_config)

    @property
    def cvd_tools_path(self):
        """Return string of the path to the cvd tools."""
        return self._cvd_tools_path

    @property
    def x_res(self):
        """Return x_res."""
        return self._x_res

    @property
    def y_res(self):
        """Return y_res."""
        return self._y_res

    @property
    def dpi(self):
        """Return dpi."""
        return self._dpi

    @property
    def adb_ip_port(self):
        """Return adb_ip_port."""
        return self._adb_ip_port

    @property
    def instance_dir(self):
        """Return instance_dir."""
        return self._instance_dir

    @property
    def vnc_port(self):
        """Return vnc_port."""
        return self._vnc_port

    @property
    def adb_port(self):
        """Return adb_port."""
        return self._adb_port
