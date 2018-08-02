#!/usr/bin/python
#
# Copyright 2018 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Main entry point for all of acloud's unittest."""

from importlib import import_module
import os
import sys
import unittest


def GetTestModules():
    """Return list of testable modules.

    We need to find all the test files (*_test.py) and get their relative
    path (internal/lib/utils_test.py) and translate it to an import path and
    strip the py ext (internal.lib.utils_test).

    Returns:
        List of strings (the testable module import path).
    """
    testable_modules = []
    base_path = os.path.dirname(os.path.realpath(__file__))

    # Get list of all python files that end in _test.py (except for __file__).
    for dirpath, _, files in os.walk(base_path):
        for f in files:
            if f.endswith("_test.py") and f != os.path.basename(__file__):
                # Now transform it into a relative import path.
                full_file_path = os.path.join(dirpath, f)
                rel_file_path = os.path.relpath(full_file_path, base_path)
                rel_file_path, _ = os.path.splitext(rel_file_path)
                rel_file_path = rel_file_path.replace(os.sep, ".")
                testable_modules.append(rel_file_path)

    return testable_modules


def main(_):
    """Main unittest entry.

    Args:
        argv: A list of system arguments. (unused)

    Returns:
        0 if success. None-zero if fails.
    """
    test_modules = GetTestModules()
    for mod in test_modules:
        import_module(mod)

    loader = unittest.defaultTestLoader
    test_suite = loader.loadTestsFromNames(test_modules)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    sys.exit(not result.wasSuccessful())


if __name__ == '__main__':
    main(sys.argv[1:])
