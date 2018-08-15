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

from acloud.create import avd_spec
from acloud.create import base_avd_create


def Run(args):
    """Run create.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    spec = avd_spec.AVDSpec(args)
    avd_creator = base_avd_create.BaseAVDCreate()
    avd_creator.Create(spec)
