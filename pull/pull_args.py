#!/usr/bin/env python
#
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
r"""Pull args.

Defines the pull arg parser that holds pull specific args.
"""
import argparse


CMD_PULL = "pull"


def GetPullArgParser(subparser):
    """Return the pull arg parser.

    Args:
       subparser: argparse.ArgumentParser that is attached to main acloud cmd.

    Returns:
        argparse.ArgumentParser with pull options defined.
    """
    pull_parser = subparser.add_parser(CMD_PULL)
    pull_parser.required = False
    pull_parser.set_defaults(which=CMD_PULL)
    pull_group = pull_parser.add_mutually_exclusive_group()
    pull_group.add_argument(
        "--instance-name",
        dest="instance_name",
        type=str,
        required=False,
        help="The name of the remote instance that need to pull log files.")

    # TODO(b/118439885): Old arg formats to support transition, delete when
    # transistion is done.
    pull_group.add_argument(
        "--instance_name",
        dest="instance_name",
        type=str,
        required=False,
        help=argparse.SUPPRESS)

    return pull_parser
