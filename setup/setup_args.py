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
r"""Setup args.

Defines the setup arg parser that holds setup specific args.
"""

CMD_SETUP = "setup"


def GetSetupArgParser(subparser):
    """Return the setup arg parser.

    Args:
       subparser: argparse.ArgumentParser that is attached to main acloud cmd.

    Returns:
        argparse.ArgumentParser with setup options defined.
    """
    setup_parser = subparser.add_parser(CMD_SETUP)
    setup_parser.required = False
    setup_parser.set_defaults(which=CMD_SETUP)
    return setup_parser
