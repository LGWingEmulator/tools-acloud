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
"""Common Utilities."""

from __future__ import print_function

from distutils.spawn import find_executable
import base64
import binascii
import collections
import errno
import getpass
import logging
import os
import shutil
import struct
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
import zipfile

from acloud import errors as root_errors
from acloud.internal import constants
from acloud.public import errors

logger = logging.getLogger(__name__)

SSH_KEYGEN_CMD = ["ssh-keygen", "-t", "rsa", "-b", "4096"]
SSH_KEYGEN_PUB_CMD = ["ssh-keygen", "-y"]
DEFAULT_RETRY_BACKOFF_FACTOR = 1
DEFAULT_SLEEP_MULTIPLIER = 0

SSH_BIN = "ssh"
_SSH_TUNNEL_ARGS = ("-i %(rsa_key_file)s -o UserKnownHostsFile=/dev/null "
                    "-o StrictHostKeyChecking=no "
                    "-L %(vnc_port)d:127.0.0.1:%(target_vnc_port)d "
                    "-L %(adb_port)d:127.0.0.1:%(target_adb_port)d "
                    "-N -f -l %(ssh_user)s %(ip_addr)s")
ADB_BIN = "adb"
_ADB_CONNECT_ARGS = "connect 127.0.0.1:%(adb_port)d"
# Store the ports that vnc/adb are forwarded to, both are integers.
ForwardedPorts = collections.namedtuple("ForwardedPorts", [constants.VNC_PORT,
                                                           constants.ADB_PORT])

class TempDir(object):
    """A context manager that ceates a temporary directory.

    Attributes:
        path: The path of the temporary directory.
    """

    def __init__(self):
        self.path = tempfile.mkdtemp()
        os.chmod(self.path, 0o700)
        logger.debug("Created temporary dir %s", self.path)

    def __enter__(self):
        """Enter."""
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit.

        Args:
            exc_type: Exception type raised within the context manager.
                      None if no execption is raised.
            exc_value: Exception instance raised within the context manager.
                       None if no execption is raised.
            traceback: Traceback for exeception that is raised within
                       the context manager.
                       None if no execption is raised.
        Raises:
            EnvironmentError or OSError when failed to delete temp directory.
        """
        try:
            if self.path:
                shutil.rmtree(self.path)
                logger.debug("Deleted temporary dir %s", self.path)
        except EnvironmentError as e:
            # Ignore error if there is no exception raised
            # within the with-clause and the EnvironementError is
            # about problem that directory or file does not exist.
            if not exc_type and e.errno != errno.ENOENT:
                raise
        except Exception as e:  # pylint: disable=W0703
            if exc_type:
                logger.error(
                    "Encountered error while deleting %s: %s",
                    self.path,
                    str(e),
                    exc_info=True)
            else:
                raise


def RetryOnException(retry_checker,
                     max_retries,
                     sleep_multiplier=0,
                     retry_backoff_factor=1):
    """Decorater which retries the function call if |retry_checker| returns true.

    Args:
        retry_checker: A callback function which should take an exception instance
                       and return True if functor(*args, **kwargs) should be retried
                       when such exception is raised, and return False if it should
                       not be retried.
        max_retries: Maximum number of retries allowed.
        sleep_multiplier: Will sleep sleep_multiplier * attempt_count seconds if
                          retry_backoff_factor is 1.  Will sleep
                          sleep_multiplier * (
                              retry_backoff_factor ** (attempt_count -  1))
                          if retry_backoff_factor != 1.
        retry_backoff_factor: See explanation of sleep_multiplier.

    Returns:
        The function wrapper.
    """

    def _Wrapper(func):
        def _FunctionWrapper(*args, **kwargs):
            return Retry(retry_checker, max_retries, func, sleep_multiplier,
                         retry_backoff_factor, *args, **kwargs)

        return _FunctionWrapper

    return _Wrapper


def Retry(retry_checker, max_retries, functor, sleep_multiplier,
          retry_backoff_factor, *args, **kwargs):
    """Conditionally retry a function.

    Args:
        retry_checker: A callback function which should take an exception instance
                       and return True if functor(*args, **kwargs) should be retried
                       when such exception is raised, and return False if it should
                       not be retried.
        max_retries: Maximum number of retries allowed.
        functor: The function to call, will call functor(*args, **kwargs).
        sleep_multiplier: Will sleep sleep_multiplier * attempt_count seconds if
                          retry_backoff_factor is 1.  Will sleep
                          sleep_multiplier * (
                              retry_backoff_factor ** (attempt_count -  1))
                          if retry_backoff_factor != 1.
        retry_backoff_factor: See explanation of sleep_multiplier.
        *args: Arguments to pass to the functor.
        **kwargs: Key-val based arguments to pass to the functor.

    Returns:
        The return value of the functor.

    Raises:
        Exception: The exception that functor(*args, **kwargs) throws.
    """
    attempt_count = 0
    while attempt_count <= max_retries:
        try:
            attempt_count += 1
            return_value = functor(*args, **kwargs)
            return return_value
        except Exception as e:  # pylint: disable=W0703
            if retry_checker(e) and attempt_count <= max_retries:
                if retry_backoff_factor != 1:
                    sleep = sleep_multiplier * (retry_backoff_factor**
                                                (attempt_count - 1))
                else:
                    sleep = sleep_multiplier * attempt_count
                time.sleep(sleep)
            else:
                raise


def RetryExceptionType(exception_types, max_retries, functor, *args, **kwargs):
    """Retry exception if it is one of the given types.

    Args:
        exception_types: A tuple of exception types, e.g. (ValueError, KeyError)
        max_retries: Max number of retries allowed.
        functor: The function to call. Will be retried if exception is raised and
                 the exception is one of the exception_types.
        *args: Arguments to pass to Retry function.
        **kwargs: Key-val based arguments to pass to Retry functions.

    Returns:
        The value returned by calling functor.
    """
    return Retry(lambda e: isinstance(e, exception_types), max_retries,
                 functor, *args, **kwargs)


def PollAndWait(func, expected_return, timeout_exception, timeout_secs,
                sleep_interval_secs, *args, **kwargs):
    """Call a function until the function returns expected value or times out.

    Args:
        func: Function to call.
        expected_return: The expected return value.
        timeout_exception: Exception to raise when it hits timeout.
        timeout_secs: Timeout seconds.
                      If 0 or less than zero, the function will run once and
                      we will not wait on it.
        sleep_interval_secs: Time to sleep between two attemps.
        *args: list of args to pass to func.
        **kwargs: dictionary of keyword based args to pass to func.

    Raises:
        timeout_exception: if the run of function times out.
    """
    # TODO(fdeng): Currently this method does not kill
    # |func|, if |func| takes longer than |timeout_secs|.
    # We can use a more robust version from chromite.
    start = time.time()
    while True:
        return_value = func(*args, **kwargs)
        if return_value == expected_return:
            return
        elif time.time() - start > timeout_secs:
            raise timeout_exception
        else:
            if sleep_interval_secs > 0:
                time.sleep(sleep_interval_secs)


def GenerateUniqueName(prefix=None, suffix=None):
    """Generate a random unique name using uuid4.

    Args:
        prefix: String, desired prefix to prepend to the generated name.
        suffix: String, desired suffix to append to the generated name.

    Returns:
        String, a random name.
    """
    name = uuid.uuid4().hex
    if prefix:
        name = "-".join([prefix, name])
    if suffix:
        name = "-".join([name, suffix])
    return name


def MakeTarFile(src_dict, dest):
    """Archive files in tar.gz format to a file named as |dest|.

    Args:
        src_dict: A dictionary that maps a path to be archived
                  to the corresponding name that appears in the archive.
        dest: String, path to output file, e.g. /tmp/myfile.tar.gz
    """
    logger.info("Compressing %s into %s.", src_dict.keys(), dest)
    with tarfile.open(dest, "w:gz") as tar:
        for src, arcname in src_dict.iteritems():
            tar.add(src, arcname=arcname)


def CreateSshKeyPairIfNotExist(private_key_path, public_key_path):
    """Create the ssh key pair if they don't exist.

    Case1. If the private key doesn't exist, we will create both the public key
           and the private key.
    Case2. If the private key exists but public key doesn't, we will create the
           public key by using the private key.
    Case3. If the public key exists but the private key doesn't, we will create
           a new private key and overwrite the public key.

    Args:
        private_key_path: Path to the private key file.
                          e.g. ~/.ssh/acloud_rsa
        public_key_path: Path to the public key file.
                         e.g. ~/.ssh/acloud_rsa.pub

    Raises:
        error.DriverError: If failed to create the key pair.
    """
    public_key_path = os.path.expanduser(public_key_path)
    private_key_path = os.path.expanduser(private_key_path)
    public_key_exist = os.path.exists(public_key_path)
    private_key_exist = os.path.exists(private_key_path)
    if public_key_exist and private_key_exist:
        logger.debug(
            "The ssh private key (%s) and public key (%s) already exist,"
            "will not automatically create the key pairs.", private_key_path,
            public_key_path)
        return
    key_folder = os.path.dirname(private_key_path)
    if not os.path.exists(key_folder):
        os.makedirs(key_folder)
    try:
        if private_key_exist:
            cmd = SSH_KEYGEN_PUB_CMD + ["-f", private_key_path]
            with open(public_key_path, 'w') as outfile:
                stream_content = subprocess.check_output(cmd)
                outfile.write(
                    stream_content.rstrip('\n') + " " + getpass.getuser())
            logger.info(
                "The ssh public key (%s) do not exist, "
                "automatically creating public key, calling: %s",
                public_key_path, " ".join(cmd))
        else:
            cmd = SSH_KEYGEN_CMD + [
                "-C", getpass.getuser(), "-f", private_key_path
            ]
            logger.info(
                "Creating public key from private key (%s) via cmd: %s",
                private_key_path, " ".join(cmd))
            subprocess.check_call(cmd, stdout=sys.stderr, stderr=sys.stdout)
    except subprocess.CalledProcessError as e:
        raise errors.DriverError("Failed to create ssh key pair: %s" % str(e))
    except OSError as e:
        raise errors.DriverError(
            "Failed to create ssh key pair, please make sure "
            "'ssh-keygen' is installed: %s" % str(e))

    # By default ssh-keygen will create a public key file
    # by append .pub to the private key file name. Rename it
    # to what's requested by public_key_path.
    default_pub_key_path = "%s.pub" % private_key_path
    try:
        if default_pub_key_path != public_key_path:
            os.rename(default_pub_key_path, public_key_path)
    except OSError as e:
        raise errors.DriverError(
            "Failed to rename %s to %s: %s" % (default_pub_key_path,
                                               public_key_path, str(e)))

    logger.info("Created ssh private key (%s) and public key (%s)",
                private_key_path, public_key_path)


def VerifyRsaPubKey(rsa):
    """Verify the format of rsa public key.

    Args:
        rsa: content of rsa public key. It should follow the format of
             ssh-rsa AAAAB3NzaC1yc2EA.... test@test.com

    Raises:
        DriverError if the format is not correct.
    """
    if not rsa or not all(ord(c) < 128 for c in rsa):
        raise errors.DriverError(
            "rsa key is empty or contains non-ascii character: %s" % rsa)

    elements = rsa.split()
    if len(elements) != 3:
        raise errors.DriverError("rsa key is invalid, wrong format: %s" % rsa)

    key_type, data, _ = elements
    try:
        binary_data = base64.decodestring(data)
        # number of bytes of int type
        int_length = 4
        # binary_data is like "7ssh-key..." in a binary format.
        # The first 4 bytes should represent 7, which should be
        # the length of the following string "ssh-key".
        # And the next 7 bytes should be string "ssh-key".
        # We will verify that the rsa conforms to this format.
        # ">I" in the following line means "big-endian unsigned integer".
        type_length = struct.unpack(">I", binary_data[:int_length])[0]
        if binary_data[int_length:int_length + type_length] != key_type:
            raise errors.DriverError("rsa key is invalid: %s" % rsa)
    except (struct.error, binascii.Error) as e:
        raise errors.DriverError(
            "rsa key is invalid: %s, error: %s" % (rsa, str(e)))

def Decompress(sourcefile, dest=None):
    """Decompress .zip or .tar.gz.

    Args:
        sourcefile: A string, a source file path to decompress.
        dest: A string, a folder path as decompress destination.

    Raises:
        errors.UnsupportedCompressionFileType: Not supported extension.
    """
    logger.info("Start to decompress %s!", sourcefile)
    dest_path = dest if dest else "."
    if sourcefile.endswith(".tar.gz"):
        with tarfile.open(sourcefile, "r:gz") as compressor:
            compressor.extractall(dest_path)
    elif sourcefile.endswith(".zip"):
        with zipfile.ZipFile(sourcefile, 'r') as compressor:
            compressor.extractall(dest_path)
    else:
        raise root_errors.UnsupportedCompressionFileType(
            "Sorry, we could only support compression file type "
            "for zip or tar.gz.")

# pylint: disable=old-style-class,no-init
class TextColors:
    """A class that defines common color ANSI code."""

    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def PrintColorString(message, colors=TextColors.OKBLUE, **kwargs):
    """A helper function to print out colored text.

    Use print function "print(message, end="")" to show message in one line.
    Example code:
        DisplayMessages("Creating GCE instance...", end="")
        # Job execute 20s
        DisplayMessages("Done! (20s)")
    Display:
        Creating GCE instance...
        # After job finished, messages update as following:
        Creating GCE instance...Done! (20s)

    Args:
        message: String, the message text.
        colors: String, color code.
        **kwargs: dictionary of keyword based args to pass to func.
    """
    print(colors + message + TextColors.ENDC, **kwargs)
    sys.stdout.flush()


def InteractWithQuestion(question, colors=TextColors.WARNING):
    """A helper function to define the common way to run interactive cmd.

    Args:
        question: String, the question to ask user.
        colors: String, color code.

    Returns:
        String, input from user.
    """
    return str(raw_input(colors + question + TextColors.ENDC).strip())


def GetUserAnswerYes(question):
    """Ask user about acloud setup question.

    Args:
        question: String, ask question for user.
            Ex: "Are you sure to change bucket name:[y/n]"

    Returns:
        Boolean, True if answer is "Yes", False otherwise.
    """
    answer = InteractWithQuestion(question)
    return answer.lower() in constants.USER_ANSWER_YES


class BatchHttpRequestExecutor(object):
    """A helper class that executes requests in batch with retry.

    This executor executes http requests in a batch and retry
    those that have failed. It iteratively updates the dictionary
    self._final_results with latest results, which can be retrieved
    via GetResults.
    """

    def __init__(self,
                 execute_once_functor,
                 requests,
                 retry_http_codes=None,
                 max_retry=None,
                 sleep=None,
                 backoff_factor=None,
                 other_retriable_errors=None):
        """Initializes the executor.

        Args:
            execute_once_functor: A function that execute requests in batch once.
                                  It should return a dictionary like
                                  {request_id: (response, exception)}
            requests: A dictionary where key is request id picked by caller,
                      and value is a apiclient.http.HttpRequest.
            retry_http_codes: A list of http codes to retry.
            max_retry: See utils.Retry.
            sleep: See utils.Retry.
            backoff_factor: See utils.Retry.
            other_retriable_errors: A tuple of error types that should be retried
                                    other than errors.HttpError.
        """
        self._execute_once_functor = execute_once_functor
        self._requests = requests
        # A dictionary that maps request id to pending request.
        self._pending_requests = {}
        # A dictionary that maps request id to a tuple (response, exception).
        self._final_results = {}
        self._retry_http_codes = retry_http_codes
        self._max_retry = max_retry
        self._sleep = sleep
        self._backoff_factor = backoff_factor
        self._other_retriable_errors = other_retriable_errors

    def _ShoudRetry(self, exception):
        """Check if an exception is retriable.

        Args:
            exception: An exception instance.
        """
        if isinstance(exception, self._other_retriable_errors):
            return True

        if (isinstance(exception, errors.HttpError)
                and exception.code in self._retry_http_codes):
            return True
        return False

    def _ExecuteOnce(self):
        """Executes pending requests and update it with failed, retriable ones.

        Raises:
            HasRetriableRequestsError: if some requests fail and are retriable.
        """
        results = self._execute_once_functor(self._pending_requests)
        # Update final_results with latest results.
        self._final_results.update(results)
        # Clear pending_requests
        self._pending_requests.clear()
        for request_id, result in results.iteritems():
            exception = result[1]
            if exception is not None and self._ShoudRetry(exception):
                # If this is a retriable exception, put it in pending_requests
                self._pending_requests[request_id] = self._requests[request_id]
        if self._pending_requests:
            # If there is still retriable requests pending, raise an error
            # so that Retry will retry this function with pending_requests.
            raise errors.HasRetriableRequestsError(
                "Retriable errors: %s" %
                [str(results[rid][1]) for rid in self._pending_requests])

    def Execute(self):
        """Executes the requests and retry if necessary.

        Will populate self._final_results.
        """

        def _ShouldRetryHandler(exc):
            """Check if |exc| is a retriable exception.

            Args:
                exc: An exception.

            Returns:
                True if exception is of type HasRetriableRequestsError; False otherwise.
            """
            should_retry = isinstance(exc, errors.HasRetriableRequestsError)
            if should_retry:
                logger.info("Will retry failed requests.", exc_info=True)
                logger.info("%s", exc)
            return should_retry

        try:
            self._pending_requests = self._requests.copy()
            Retry(
                _ShouldRetryHandler,
                max_retries=self._max_retry,
                functor=self._ExecuteOnce,
                sleep_multiplier=self._sleep,
                retry_backoff_factor=self._backoff_factor)
        except errors.HasRetriableRequestsError:
            logger.debug("Some requests did not succeed after retry.")

    def GetResults(self):
        """Returns final results.

        Returns:
            results, a dictionary in the following format
            {request_id: (response, exception)}
            request_ids are those from requests; response
            is the http response for the request or None on error;
            exception is an instance of DriverError or None if no error.
        """
        return self._final_results


class TimeExecute(object):
    """Count the function execute time."""

    def __init__(self, function_description=None, print_before_call=True, print_status=True):
        """Initializes the class.

        Args:
            function_description: String that describes function (e.g."Creating
                                  Instance...")
            print_before_call: Boolean, print the function description before
                               calling the function, default True.
            print_status: Boolean, print the status of the function after the
                          function has completed, default True ("OK" or "Fail").
        """
        self._function_description = function_description
        self._print_before_call = print_before_call
        self._print_status = print_status

    def __call__(self, func):
        def DecoratorFunction(*args, **kargs):
            """Decorator function.

            Args:
                *args: Arguments to pass to the functor.
                **kwargs: Key-val based arguments to pass to the functor.

            Raises:
                Exception: The exception that functor(*args, **kwargs) throws.
            """
            timestart = time.time()
            if self._print_before_call:
                PrintColorString("%s ..."% self._function_description, end="")
            try:
                result = func(*args, **kargs)
                if not self._print_before_call:
                    PrintColorString("%s (%ds)" % (self._function_description,
                                                   time.time()-timestart),
                                     TextColors.OKGREEN)
                if self._print_status:
                    PrintColorString("OK! (%ds)" % (time.time()-timestart),
                                     TextColors.OKGREEN)
                return result
            except:
                if self._print_status:
                    PrintColorString("Fail! (%ds)" % (time.time()-timestart),
                                     TextColors.FAIL)
                raise
        return DecoratorFunction


def PickFreePort():
    """Helper to pick a free port.

    Returns:
        Integer, a free port number.
    """
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind(("", 0))
    port = tcp_socket.getsockname()[1]
    tcp_socket.close()
    return port


def _ExecuteCommand(cmd, args):
    """Execute command.

    Args:
        cmd: Strings of execute binary name.
        args: List of args to pass in with cmd.

    Raises:
        errors.NoExecuteBin: Can't find the execute bin file.
    """
    bin_path = find_executable(cmd)
    if not bin_path:
        raise root_errors.NoExecuteCmd("unable to locate %s" % cmd)
    command = [bin_path] + args
    logger.debug("Running '%s'", ' '.join(command))
    with open(os.devnull, "w") as dev_null:
        subprocess.check_call(command, stderr=dev_null, stdout=dev_null)


# pylint: disable=too-many-locals
def AutoConnect(ip_addr, rsa_key_file, target_vnc_port, target_adb_port, ssh_user):
    """Autoconnect to an AVD instance.

    Args:
        ip_addr: String, use to build the adb & vnc tunnel between local
                 and remote instance.
        rsa_key_file: String, Private key file path to use when creating
                      the ssh tunnels.
        target_vnc_port: Integer of target vnc port number.
        target_adb_port: Integer of target adb port number.
        ssh_user: String of user login into the instance.

    Returns:
        NamedTuple of (vnc_port, adb_port) SSHTUNNEL of the connect, both are
        integers.
    """
    local_free_vnc_port = PickFreePort()
    local_free_adb_port = PickFreePort()
    try:
        ssh_tunnel_args = _SSH_TUNNEL_ARGS % {
            "rsa_key_file": rsa_key_file,
            "vnc_port": local_free_vnc_port,
            "adb_port": local_free_adb_port,
            "target_vnc_port": target_vnc_port,
            "target_adb_port": target_adb_port,
            "ssh_user": ssh_user,
            "ip_addr": ip_addr}
        _ExecuteCommand(SSH_BIN, ssh_tunnel_args.split())
    except subprocess.CalledProcessError:
        PrintColorString("Failed to create ssh tunnels, retry with '#acloud "
                         "reconnect'.", TextColors.FAIL)
    try:
        adb_connect_args = _ADB_CONNECT_ARGS % {"adb_port": local_free_adb_port}
        _ExecuteCommand(ADB_BIN, adb_connect_args.split())
    except subprocess.CalledProcessError:
        PrintColorString("Failed to adb connect, retry with "
                         "'#acloud reconnect'", TextColors.FAIL)

    return ForwardedPorts(vnc_port=local_free_vnc_port,
                          adb_port=local_free_adb_port)
