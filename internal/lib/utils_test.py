#!/usr/bin/env python
#
# Copyright 2016 - The Android Open Source Project
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
"""Tests for acloud.internal.lib.utils."""

import errno
import getpass
import os
import shutil
import subprocess
import tempfile
import time
import Tkinter

import unittest
import mock

from acloud.internal.lib import driver_test_lib
from acloud.internal.lib import utils


class UtilsTest(driver_test_lib.BaseDriverTest):
    """Test Utils."""

    def TestTempDirSuccess(self):
        """Test create a temp dir."""
        self.Patch(os, "chmod")
        self.Patch(tempfile, "mkdtemp", return_value="/tmp/tempdir")
        self.Patch(shutil, "rmtree")
        with utils.TempDir():
            pass
        # Verify.
        tempfile.mkdtemp.assert_called_once()  # pylint: disable=no-member
        shutil.rmtree.assert_called_with("/tmp/tempdir")  # pylint: disable=no-member

    def TestTempDirExceptionRaised(self):
        """Test create a temp dir and exception is raised within with-clause."""
        self.Patch(os, "chmod")
        self.Patch(tempfile, "mkdtemp", return_value="/tmp/tempdir")
        self.Patch(shutil, "rmtree")

        class ExpectedException(Exception):
            """Expected exception."""
            pass

        def _Call():
            with utils.TempDir():
                raise ExpectedException("Expected exception.")

        # Verify. ExpectedException should be raised.
        self.assertRaises(ExpectedException, _Call)
        tempfile.mkdtemp.assert_called_once()  # pylint: disable=no-member
        shutil.rmtree.assert_called_with("/tmp/tempdir")  #pylint: disable=no-member

    def testTempDirWhenDeleteTempDirNoLongerExist(self):  # pylint: disable=invalid-name
        """Test create a temp dir and dir no longer exists during deletion."""
        self.Patch(os, "chmod")
        self.Patch(tempfile, "mkdtemp", return_value="/tmp/tempdir")
        expected_error = EnvironmentError()
        expected_error.errno = errno.ENOENT
        self.Patch(shutil, "rmtree", side_effect=expected_error)

        def _Call():
            with utils.TempDir():
                pass

        # Verify no exception should be raised when rmtree raises
        # EnvironmentError with errno.ENOENT, i.e.
        # directory no longer exists.
        _Call()
        tempfile.mkdtemp.assert_called_once()  #pylint: disable=no-member
        shutil.rmtree.assert_called_with("/tmp/tempdir")  #pylint: disable=no-member

    def testTempDirWhenDeleteEncounterError(self):
        """Test create a temp dir and encoutered error during deletion."""
        self.Patch(os, "chmod")
        self.Patch(tempfile, "mkdtemp", return_value="/tmp/tempdir")
        expected_error = OSError("Expected OS Error")
        self.Patch(shutil, "rmtree", side_effect=expected_error)

        def _Call():
            with utils.TempDir():
                pass

        # Verify OSError should be raised.
        self.assertRaises(OSError, _Call)
        tempfile.mkdtemp.assert_called_once()  #pylint: disable=no-member
        shutil.rmtree.assert_called_with("/tmp/tempdir")  #pylint: disable=no-member

    def testTempDirOrininalErrorRaised(self):
        """Test original error is raised even if tmp dir deletion failed."""
        self.Patch(os, "chmod")
        self.Patch(tempfile, "mkdtemp", return_value="/tmp/tempdir")
        expected_error = OSError("Expected OS Error")
        self.Patch(shutil, "rmtree", side_effect=expected_error)

        class ExpectedException(Exception):
            """Expected exception."""
            pass

        def _Call():
            with utils.TempDir():
                raise ExpectedException("Expected Exception")

        # Verify.
        # ExpectedException should be raised, and OSError
        # should not be raised.
        self.assertRaises(ExpectedException, _Call)
        tempfile.mkdtemp.assert_called_once()  #pylint: disable=no-member
        shutil.rmtree.assert_called_with("/tmp/tempdir")  #pylint: disable=no-member

    def testCreateSshKeyPairKeyAlreadyExists(self):  #pylint: disable=invalid-name
        """Test when the key pair already exists."""
        public_key = "/fake/public_key"
        private_key = "/fake/private_key"
        self.Patch(os.path, "exists", side_effect=[True, True])
        self.Patch(subprocess, "check_call")
        self.Patch(os, "makedirs", return_value=True)
        utils.CreateSshKeyPairIfNotExist(private_key, public_key)
        self.assertEqual(subprocess.check_call.call_count, 0)  #pylint: disable=no-member

    def testCreateSshKeyPairKeyAreCreated(self):
        """Test when the key pair created."""
        public_key = "/fake/public_key"
        private_key = "/fake/private_key"
        self.Patch(os.path, "exists", return_value=False)
        self.Patch(os, "makedirs", return_value=True)
        self.Patch(subprocess, "check_call")
        self.Patch(os, "rename")
        utils.CreateSshKeyPairIfNotExist(private_key, public_key)
        self.assertEqual(subprocess.check_call.call_count, 1)  #pylint: disable=no-member
        subprocess.check_call.assert_called_with(  #pylint: disable=no-member
            utils.SSH_KEYGEN_CMD +
            ["-C", getpass.getuser(), "-f", private_key],
            stdout=mock.ANY,
            stderr=mock.ANY)

    def testCreatePublicKeyAreCreated(self):
        """Test when the PublicKey created."""
        public_key = "/fake/public_key"
        private_key = "/fake/private_key"
        self.Patch(os.path, "exists", side_effect=[False, True, True])
        self.Patch(os, "makedirs", return_value=True)
        mock_open = mock.mock_open(read_data=public_key)
        self.Patch(subprocess, "check_output")
        self.Patch(os, "rename")
        with mock.patch("__builtin__.open", mock_open):
            utils.CreateSshKeyPairIfNotExist(private_key, public_key)
        self.assertEqual(subprocess.check_output.call_count, 1)  #pylint: disable=no-member
        subprocess.check_output.assert_called_with(  #pylint: disable=no-member
            utils.SSH_KEYGEN_PUB_CMD +["-f", private_key])

    def TestRetryOnException(self):
        """Test Retry."""

        def _IsValueError(exc):
            return isinstance(exc, ValueError)

        num_retry = 5

        @utils.RetryOnException(_IsValueError, num_retry)
        def _RaiseAndRetry(sentinel):
            sentinel.alert()
            raise ValueError("Fake error.")

        sentinel = mock.MagicMock()
        self.assertRaises(ValueError, _RaiseAndRetry, sentinel)
        self.assertEqual(1 + num_retry, sentinel.alert.call_count)

    def testRetryExceptionType(self):
        """Test RetryExceptionType function."""

        def _RaiseAndRetry(sentinel):
            sentinel.alert()
            raise ValueError("Fake error.")

        num_retry = 5
        sentinel = mock.MagicMock()
        self.assertRaises(
            ValueError,
            utils.RetryExceptionType, (KeyError, ValueError),
            num_retry,
            _RaiseAndRetry,
            0, # sleep_multiplier
            1, # retry_backoff_factor
            sentinel=sentinel)
        self.assertEqual(1 + num_retry, sentinel.alert.call_count)

    def testRetry(self):
        """Test Retry."""
        mock_sleep = self.Patch(time, "sleep")

        def _RaiseAndRetry(sentinel):
            sentinel.alert()
            raise ValueError("Fake error.")

        num_retry = 5
        sentinel = mock.MagicMock()
        self.assertRaises(
            ValueError,
            utils.RetryExceptionType, (ValueError, KeyError),
            num_retry,
            _RaiseAndRetry,
            1, # sleep_multiplier
            2, # retry_backoff_factor
            sentinel=sentinel)

        self.assertEqual(1 + num_retry, sentinel.alert.call_count)
        mock_sleep.assert_has_calls(
            [
                mock.call(1),
                mock.call(2),
                mock.call(4),
                mock.call(8),
                mock.call(16)
            ])

    @mock.patch("__builtin__.raw_input")
    def testGetAnswerFromList(self, mock_raw_input):
        """Test GetAnswerFromList."""
        answer_list = ["image1.zip", "image2.zip", "image3.zip"]
        mock_raw_input.return_value = 0
        with self.assertRaises(SystemExit):
            utils.GetAnswerFromList(answer_list)
        mock_raw_input.side_effect = [1, 2, 3, 1]
        self.assertEqual(utils.GetAnswerFromList(answer_list),
                         ["image1.zip"])
        self.assertEqual(utils.GetAnswerFromList(answer_list),
                         ["image2.zip"])
        self.assertEqual(utils.GetAnswerFromList(answer_list),
                         ["image3.zip"])
        self.assertEqual(utils.GetAnswerFromList(answer_list,
                                                 enable_choose_all=True),
                         answer_list)

    @mock.patch.object(Tkinter.Tk, "winfo_screenwidth")
    @mock.patch.object(Tkinter.Tk, "winfo_screenheight")
    def testCalculateVNCScreenRatio(self, mock_screenheight, mock_screenwidth):
        """Test Calculating the scale ratio of VNC display."""
        # Tkinter.Tk requires $DISPLAY to be set if the screenName is None so
        # set screenName to avoid TclError when running this test in a term that
        # doesn't have $DISPLAY set.
        mock.patch.object(Tkinter, "Tk", new=Tkinter.Tk(screenName=":0"))

        # Get scale-down ratio if screen height is smaller than AVD height.
        mock_screenheight.return_value = 800
        mock_screenwidth.return_value = 1200
        avd_h = 1920
        avd_w = 1080
        self.assertEqual(utils.CalculateVNCScreenRatio(avd_w, avd_h), 0.4)

        # Get scale-down ratio if screen width is smaller than AVD width.
        mock_screenheight.return_value = 800
        mock_screenwidth.return_value = 1200
        avd_h = 900
        avd_w = 1920
        self.assertEqual(utils.CalculateVNCScreenRatio(avd_w, avd_h), 0.6)

        # Scale ratio = 1 if screen is larger than AVD.
        mock_screenheight.return_value = 1080
        mock_screenwidth.return_value = 1920
        avd_h = 800
        avd_w = 1280
        self.assertEqual(utils.CalculateVNCScreenRatio(avd_w, avd_h), 1)

        # Get the scale if ratio of width is smaller than the
        # ratio of height.
        mock_screenheight.return_value = 1200
        mock_screenwidth.return_value = 800
        avd_h = 1920
        avd_w = 1080
        self.assertEqual(utils.CalculateVNCScreenRatio(avd_w, avd_h), 0.6)


if __name__ == "__main__":
    unittest.main()
