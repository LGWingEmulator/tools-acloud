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

from acloud.internal.lib import utils
from acloud.setup import host_setup_runner
from acloud.setup import gcp_setup_runner


def Run(args):
    """Run setup.

    Setup options:
        -host: Setup host settings.
        -gcp_init: Setup gcp settings.
        -None, default behavior will setup host and gcp settings.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    # Setup process will be in the following manner:
    # 1.Print welcome message.
    _PrintWelcomeMessage()

    # 2.Init all subtasks in queue and traverse them.
    host_runner = host_setup_runner.AvdPkgInstaller()
    host_env_runner = host_setup_runner.CuttlefishHostSetup()
    gcp_runner = gcp_setup_runner.GcpTaskRunner(args.config_file)
    task_queue = []
    if args.host or not args.gcp_init:
        task_queue.append(host_runner)
        task_queue.append(host_env_runner)
    if args.gcp_init or not args.host:
        task_queue.append(gcp_runner)

    for subtask in task_queue:
        subtask.Run()

    # 3.Print the usage hints.
    _PrintUsage()


def _PrintWelcomeMessage():
    """Print welcome message when acloud setup been called."""

    # pylint: disable=anomalous-backslash-in-string
    asc_art = "                                    \n" \
            "   ___  _______   ____  __  _____ \n" \
            "  / _ |/ ___/ /  / __ \/ / / / _ \\ \n" \
            " / __ / /__/ /__/ /_/ / /_/ / // /  \n" \
            "/_/ |_\\___/____/\\____/\\____/____/ \n" \
            "                                  \n"

    print("\nWelcome to")
    print(asc_art)


def _PrintUsage():
    """Print cmd usage hints when acloud setup been finished."""
    utils.PrintColorString("")
    utils.PrintColorString("Setup process finished")
    utils.PrintColorString("To get started creating AVDs, run '#acloud create'")
