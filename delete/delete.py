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
r"""Delete entry point.

Delete will handle all the logic related to deleting a local/remote instance
of an Android Virtual Device.
"""

from __future__ import print_function
from distutils.spawn import find_executable
import getpass
import logging
import os
import re
import subprocess
import time

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import auth
from acloud.internal.lib import gcompute_client
from acloud.internal.lib import utils
from acloud.public import config
from acloud.public import device_driver
from acloud.public import report

logger = logging.getLogger(__name__)

_COMMAND_GET_PROCESS_ID = ["pgrep", "launch_cvd"]
_COMMAND_GET_PROCESS_COMMAND = ["ps", "-o", "command", "-p"]
_LOCAL_INS_NAME = "local-instance"
_RE_LAUNCH_CVD = re.compile(r"^(?P<launch_cvd>.+launch_cvd)(.*--daemon ).+")


def _FilterInstancesByUser(instances, user):
    """Look through the instance data and filter them.

    Args:
        user: String, username to filter on.
        instances: List of instance data. This is the response from the GCP
                   compute API for listing instances.

    Returns:
        List of strings of the instance names.
    """
    filtered_instances = []
    for instance_info in instances:
        instance_name = instance_info.get("name")
        for metadata in instance_info.get("metadata", {}).get("items", []):
            if metadata["key"] == "user" and metadata["value"] == user:
                filtered_instances.append(instance_name)
    return filtered_instances


def _FindRemoteInstances(cfg, user):
    """Find instances created by user in project specified in cfg.

    Args:
        cfg: AcloudConfig object.
        user: String, username to look for.

    Returns:
        List of strings that are instance names.
    """
    credentials = auth.CreateCredentials(cfg)
    compute_client = gcompute_client.ComputeClient(cfg, credentials)
    all_instances = compute_client.ListInstances(cfg.zone)
    return _FilterInstancesByUser(all_instances, user)


def _FindLocalInstances():
    """Get local instance name.

    If launch_cvd process exists, then return local instance name.

    Returns:
        List of instances names (strings)
    """
    if utils.IsCommandRunning(constants.CMD_LAUNCH_CVD):
        return [_LOCAL_INS_NAME]
    return []


def _GetStopCvd():
    """Get stop_cvd path.

    "stop_cvd" and "launch_cvd" are in the same folder(host package folder).
    Try to get directory of "launch_cvd" by "ps -o command -p <pid>." command.
    For example: "/tmp/bin/launch_cvd --daemon --cpus 2 ..."

    Raises:
        errors.NoExecuteCmd: Can't find stop_cvd.

    Returns:
        String of stop_cvd file path.
    """
    process_id = subprocess.check_output(_COMMAND_GET_PROCESS_ID)
    process_info = subprocess.check_output(
        _COMMAND_GET_PROCESS_COMMAND + process_id.splitlines())
    for process in process_info.splitlines():
        match = _RE_LAUNCH_CVD.match(process)
        if match:
            launch_cvd_path = match.group("launch_cvd")
            stop_cvd_cmd = os.path.join(os.path.dirname(launch_cvd_path),
                                        constants.CMD_STOP_CVD)
            if os.path.exists(stop_cvd_cmd):
                logger.debug("stop_cvd command: %s", stop_cvd_cmd)
                return stop_cvd_cmd

    default_stop_cvd = find_executable(constants.CMD_STOP_CVD)
    if default_stop_cvd:
        return default_stop_cvd

    raise errors.NoExecuteCmd("stop_cvd(%s) file doesn't exist." %
                              stop_cvd_cmd)


def _GetInstancesToDelete(cfg, del_all_instances=False):
    """Look for remote/local instances.

    We're going to query the GCP project and grep local instance for all
    instances that have the user mentioned in the metadata. If we find just
    one instance, print out the details of it and delete it. If we find more
    than 1, ask the user which one they'd like to delete unless
    del_all_instances is True, then just delete them all.

    Args:
        cfg: AcloudConfig object.
        del_all_instances: Boolean, when more than 1 instance is found,
                           delete them all if True, otherwise prompt user.

    Returns:
        List of instances names (strings).
    """

    instances_to_delete = _FindRemoteInstances(cfg, getpass.getuser())
    instances_to_delete += _FindLocalInstances()
    if instances_to_delete:
        # If we find more than 1 instance, ask user what they want to do unless
        # they specified --all.
        if (len(instances_to_delete) > 1 and not del_all_instances):
            print("Multiple instance detected, choose 1 to delete:")
            instances_to_delete = utils.GetAnswerFromList(
                instances_to_delete, enable_choose_all=True)
    return instances_to_delete


def DeleteInstances(cfg, instances_to_delete):
    """Delete instances according to instances_to_delete.

    1. Delete local instance.
    2. Delete remote instance.

    Args:
        cfg: AcloudConfig object.
        instances_to_delete: List of instances names (strings).

    Returns:
        Report instance if there are instances to delete, None otherwise.
    """
    # TODO(b/117474343): We should do a couple extra things here:
    #                    - adb disconnect
    #                    - kill ssh tunnel and ssvnc
    #                    - give details of each instance
    #                    - Give better messaging about delete.
    if not instances_to_delete:
        print("No instances to delete")
        return None

    start = time.time()
    utils.PrintColorString("Deleting %s ..." % ", ".join(instances_to_delete),
                           utils.TextColors.WARNING, end="")
    delete_report = None
    if _LOCAL_INS_NAME in instances_to_delete:
        # Stop local instances
        delete_report = DeleteLocalInstance()
        instances_to_delete.remove(_LOCAL_INS_NAME)

    if instances_to_delete:
        # TODO(119283708): We should move DeleteAndroidVirtualDevices into
        # delete.py after gce is deprecated.
        # Stop remote instances.
        delete_report = device_driver.DeleteAndroidVirtualDevices(
            cfg, instances_to_delete, delete_report)

    if delete_report.errors:
        utils.PrintColorString("Fail! (%ds)" % (time.time() - start),
                               utils.TextColors.FAIL)
        logger.debug("Delete failed: %s", delete_report.errors)
    else:
        utils.PrintColorString("OK! (%ds)" % (time.time() - start),
                               utils.TextColors.OKGREEN)
    return delete_report


def DeleteLocalInstance():
    """Delete local instance.

    Delete local instance with stop_cvd command and write delete instance
    information to report.

    Args:
        delete_report: A Report instance to record local instance deleted.

    Returns:
        A Report instance.
    """
    delete_report = report.Report(command="delete")
    try:
        with open(os.devnull, "w") as dev_null:
            subprocess.check_call(
                utils.AddUserGroupsToCmd(_GetStopCvd(),
                                         constants.LIST_CF_USER_GROUPS),
                stderr=dev_null, stdout=dev_null, shell=True)
            delete_report.SetStatus(report.Status.SUCCESS)
            device_driver.AddDeletionResultToReport(
                delete_report, [_LOCAL_INS_NAME], failed=[], error_msgs=[],
                resource_name="instance")
    except subprocess.CalledProcessError as e:
        delete_report.AddError(str(e))
        delete_report.SetStatus(report.Status.FAIL)

    return delete_report


def Run(args):
    """Run delete.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    cfg = config.GetAcloudConfig(args)
    instances_to_delete = args.instance_names
    if not instances_to_delete:
        instances_to_delete = _GetInstancesToDelete(cfg, args.all)
    return DeleteInstances(cfg, instances_to_delete)
