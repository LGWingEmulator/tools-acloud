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
r"""Pull entry point.

This command will pull the log files from a remote instance for AVD troubleshooting.
"""

from __future__ import print_function
import logging

from acloud.list import list as list_instances
from acloud.public import config
from acloud.public import report


logger = logging.getLogger(__name__)


def PullFileFromInstance(instance):
    """Pull file from remote CF instance.

    Args:
        instance: list.Instance() object.

    Returns:
        A Report instance.
    """
    # TODO(120613398): rewrite this function to pull file from the remote instance.
    print("We will pull file from the instance: %s." % instance.name)
    return report.Report(command="pull")


def Run(args):
    """Run pull.

    After pull command executed, tool will return one Report instance.
    If there is no instance to pull, just return empty Report.

    Args:
        args: Namespace object from argparse.parse_args.

    Returns:
        A Report instance.
    """
    cfg = config.GetAcloudConfig(args)
    if args.instance_name:
        instance = list_instances.GetInstancesFromInstanceNames(
            cfg, [args.instance_name])
        return PullFileFromInstance(instance[0])
    return PullFileFromInstance(list_instances.ChooseOneRemoteInstance(cfg))
