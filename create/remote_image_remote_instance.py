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
r"""RemoteImageRemoteInstance class.

Create class that is responsible for creating a remote instance AVD with a
remote image.
"""

import time

from acloud.create import base_avd_create
from acloud.internal.lib import utils
from acloud.public.actions import create_cuttlefish_action


class RemoteImageRemoteInstance(base_avd_create.BaseAVDCreate):
    """Create class for a remote image remote instance AVD."""

    def Create(self, avd_spec):
        """Create the AVD.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.

        Returns:
            A Report instance.
        """
        self.PrintAvdDetails(avd_spec)
        start = time.time()
        report = create_cuttlefish_action.CreateDevices(avd_spec=avd_spec)
        utils.PrintColorString("\n")
        utils.PrintColorString("Total time: %ds" % (time.time() - start),
                               utils.TextColors.WARNING)
        self.DisplayJobResult(report)
        return report

    @staticmethod
    def DisplayJobResult(report):
        """Get job result from report.

        -Display instance name/ip from report.data.
            report.data example:
                {'devices':[{'instance_name': 'ins-f6a34397-none-5043363',
                             'ip': u'35.234.10.162'}]}
        -Display error message from report.error.

        Args:
            report: A Report instance.
        """
        if report.data.get("devices"):
            device_data = report.data.get("devices")
            for device in device_data:
                utils.PrintColorString("instance name: %s" %
                                       device.get("instance_name"),
                                       utils.TextColors.OKGREEN)
                utils.PrintColorString("device IP: %s" % device.get("ip"),
                                       utils.TextColors.OKGREEN)

        # TODO(b/117245508): Help user to delete instance if it got created.
        if report.errors:
            error_msg = "\n".join(report.errors)
            utils.PrintColorString("Fail in:\n%s\n" % error_msg,
                                   utils.TextColors.FAIL)
