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
r"""Setup entry point.

Setup will handle all of the necessary steps to enable acloud to create a local
or remote instance of an Android Virtual Device.
"""

from __future__ import print_function


def Run(args):
    """Run setup.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    # TODO: Delete once we're actually doing setup stuff.
    print ("TODO: implement actual setup functions with these args: %s" % args)
