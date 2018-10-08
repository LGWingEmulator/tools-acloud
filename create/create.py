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
r"""Create entry point.

Create will handle all the logic related to creating a local/remote instance
an Android Virtual Device and the logic related to prepping the local/remote
image artifacts.
"""

from acloud import errors
from acloud.create import avd_spec
from acloud.create import local_image_local_instance
from acloud.create import local_image_remote_instance
from acloud.create import remote_image_remote_instance
from acloud.create import remote_image_local_instance
from acloud.internal import constants


def GetAvdCreatorClass(instance_type, image_source):
    """Return the creator class for the specified spec.

    Based on the image source and the instance type, return the proper
    creator class.

    Args:
        instance_type: String, the AVD instance type (local or remote).
        image_source: String, the source of the image (local or remote).

    Returns:
        An AVD creator class (e.g. LocalImageRemoteInstance).
    """
    if (instance_type == constants.INSTANCE_TYPE_REMOTE and
            image_source == constants.IMAGE_SRC_LOCAL):
        return local_image_remote_instance.LocalImageRemoteInstance
    if (instance_type == constants.INSTANCE_TYPE_LOCAL and
            image_source == constants.IMAGE_SRC_LOCAL):
        return local_image_local_instance.LocalImageLocalInstance
    if (instance_type == constants.INSTANCE_TYPE_REMOTE and
            image_source == constants.IMAGE_SRC_REMOTE):
        return remote_image_remote_instance.RemoteImageRemoteInstance
    if (instance_type == constants.INSTANCE_TYPE_LOCAL and
            image_source == constants.IMAGE_SRC_REMOTE):
        return remote_image_local_instance.RemoteImageLocalInstance

    raise errors.UnsupportedInstanceImageType(
        "unsupported creation of instance type: %s, image source: %s" %
        (instance_type, image_source))


def Run(args):
    """Run create.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    spec = avd_spec.AVDSpec(args)
    avd_creator_class = GetAvdCreatorClass(spec.instance_type,
                                           spec.image_source)
    avd_creator = avd_creator_class()
    report = avd_creator.Create(spec)
    if report and args.report_file:
        report.Dump(args.report_file)
