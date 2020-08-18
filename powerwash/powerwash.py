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
r"""Powerwash entry point.

This command will powerwash the AVD from a remote instance.
"""

from __future__ import print_function

from acloud import errors
from acloud.list import list as list_instances
from acloud.public import config
from acloud.public import report


def PowerwashFromInstance(instance, instance_id):
    """Powerwash AVD from remote CF instance.

    Args:
        instance: list.Instance() object.
        instance_id: Integer of the instance id.

    Returns:
        A Report instance.
    """
    # TODO(162382338): rewrite this function to powerwash AVD from the remote instance.
    print("We will powerwash AVD id (%s) from the instance: %s."
          % (instance_id, instance.name))
    return report.Report(command="powerwash")


def Run(args):
    """Run powerwash.

    After powerwash command executed, tool will return one Report instance.

    Args:
        args: Namespace object from argparse.parse_args.

    Returns:
        A Report instance.

    Raises:
        errors.CommandArgError: Lack the instance_name in args.
    """
    cfg = config.GetAcloudConfig(args)
    if args.instance_name:
        instance = list_instances.GetInstancesFromInstanceNames(
            cfg, [args.instance_name])
        return PowerwashFromInstance(instance[0], args.instance_id)
    raise errors.CommandArgError("Please assign the '--instance-name' in your command.")
