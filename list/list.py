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
r"""List entry point.

List will handle all the logic related to list a local/remote instance
of an Android Virtual Device.
"""

from __future__ import print_function
import getpass
import logging
import re
import subprocess

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import auth
from acloud.internal.lib import gcompute_client
from acloud.internal.lib import utils
from acloud.list import instance
from acloud.public import config


logger = logging.getLogger(__name__)

_COMMAND_PS_LAUNCH_CVD = ["ps", "-wweo", "lstart,cmd"]
_RE_LOCAL_INSTANCE_ID = re.compile(r".+instance_home_(?P<ins_id>\d+).+")
_RE_LOCAL_CVD_PORT = re.compile(r"^127\.0\.0\.1:65(?P<cvd_port_suffix>\d{2})\s+")


def GetActiveCVDIds():
    """Get active local cvd ids from adb devices.

    The adb port of local instance will be decided according to instance id.
    The rule of adb port will be '6520 + [instance id] - 1'. So we grep last
    two digits of port and calculate the instance id.

    Return:
        List of cvd id.
    """
    local_cvd_ids = []
    adb_cmd = [constants.ADB_BIN, "devices"]
    device_info = subprocess.check_output(adb_cmd)
    for device in device_info.splitlines():
        match = _RE_LOCAL_CVD_PORT.match(device)
        if match:
            cvd_serial = match.group("cvd_port_suffix")
            local_cvd_ids.append(int(cvd_serial) - 19)
    return local_cvd_ids


def _ProcessInstances(instance_list):
    """Get more details of remote instances.

    Args:
        instance_list: List of dicts which contain info about the remote instances,
                       they're the response from the GCP GCE api.

    Returns:
        instance_detail_list: List of instance.Instance() with detail info.
    """
    return [instance.RemoteInstance(gce_instance) for gce_instance in instance_list]


def PrintInstancesDetails(instance_list, verbose=False):
    """Display instances information.

    Example of non-verbose case:
    [1]device serial: 127.0.0.1:55685 (ins-1ff036dc-5128057-cf-x86-phone-userdebug)
    [2]device serial: 127.0.0.1:60979 (ins-80952669-5128057-cf-x86-phone-userdebug)
    [3]device serial: 127.0.0.1:6520 (local-instance)

    Example of verbose case:
    [1] name: ins-244710f0-5091715-aosp-cf-x86-phone-userdebug
        IP: None
        create time: 2018-10-25T06:32:08.182-07:00
        status: TERMINATED
        avd type: cuttlefish
        display: 1080x1920 (240)

    [2] name: ins-82979192-5091715-aosp-cf-x86-phone-userdebug
        IP: 35.232.77.15
        adb serial: 127.0.0.1:33537
        create time: 2018-10-25T06:34:22.716-07:00
        status: RUNNING
        avd type: cuttlefish
        display: 1080x1920 (240)

    Args:
        verbose: Boolean, True to print all details and only full name if False.
        instance_list: List of instances.
    """
    if not instance_list:
        print("No remote or local instances found")

    for num, instance_info in enumerate(instance_list, 1):
        idx_str = "[%d]" % num
        utils.PrintColorString(idx_str, end="")
        if verbose:
            print(instance_info.Summary())
            # add space between instances in verbose mode.
            print("")
        else:
            print(instance_info)


def GetRemoteInstances(cfg):
    """Look for remote instances.

    We're going to query the GCP project for all instances that created by user.

    Args:
        cfg: AcloudConfig object.

    Returns:
        instance_list: List of remote instances.
    """
    credentials = auth.CreateCredentials(cfg)
    compute_client = gcompute_client.ComputeClient(cfg, credentials)
    filter_item = "labels.%s=%s" % (constants.LABEL_CREATE_BY, getpass.getuser())
    all_instances = compute_client.ListInstances(instance_filter=filter_item)

    logger.debug("Instance list from: (filter: %s\n%s):",
                 filter_item, all_instances)

    return _ProcessInstances(all_instances)


def GetLocalInstances():
    """Look for local instances.

    Gather local instances information from cuttlefish runtime config.

    Returns:
        instance_list: List of local instances.
    """
    # Running instances on local is not supported on all OS.
    if not utils.IsSupportedPlatform():
        return None

    local_cvd_ids = GetActiveCVDIds()
    local_instance_list = []
    for cvd_id in local_cvd_ids:
        ins_dir = x_res = y_res = dpi = cf_runtime_config_dict = None
        try:
            cf_runtime_config_dict = instance.GetCuttlefishRuntimeConfig(cvd_id)
        except errors.ConfigError:
            logger.error("Instance[id:%d] dir not found!", cvd_id)

        if cf_runtime_config_dict:
            ins_dir = instance.GetLocalInstanceRuntimeDir(cvd_id)
            x_res = cf_runtime_config_dict["x_res"]
            y_res = cf_runtime_config_dict["y_res"]
            dpi = cf_runtime_config_dict["dpi"]
        # TODO(143063678), there's no createtime info in
        # cuttlefish_config.json so far.
        local_instance_list.append(instance.LocalInstance(cvd_id,
                                                          x_res,
                                                          y_res,
                                                          dpi,
                                                          None,
                                                          ins_dir))
    return local_instance_list


def _GetIdFromInstanceDirStr(instance_dir):
    """Look for instance id from the path of instance dir.

    Args:
        instance_dir: String, path of instance_dir.

    Returns:
        Integer of instance id.

    Raises:
        errors.InvalidInstanceDir: Invalid instance idr.
    """
    match = _RE_LOCAL_INSTANCE_ID.match(instance_dir)
    if match:
        return int(match.group("ins_id"))

    raise errors.InvalidInstanceDir("Instance dir is invalid:%s. local AVD "
                                    "launched outside acloud is not supported"
                                    % instance_dir)


def GetInstances(cfg):
    """Look for remote/local instances.

    Args:
        cfg: AcloudConfig object.

    Returns:
        instance_list: List of instances.
    """
    instances_list = GetRemoteInstances(cfg)
    local_instances = GetLocalInstances()
    if local_instances:
        instances_list.extend(local_instances)

    return instances_list


def ChooseInstances(cfg, select_all_instances=False):
    """Get instances.

    Retrieve all remote/local instances and if there is more than 1 instance
    found, ask user which instance they'd like.

    Args:
        cfg: AcloudConfig object.
        select_all_instances: True if select all instances by default and no
                              need to ask user to choose.

    Returns:
        List of list.Instance() object.
    """
    instances_list = GetInstances(cfg)
    if (len(instances_list) > 1) and not select_all_instances:
        print("Multiple instances detected, choose any one to proceed:")
        instances = utils.GetAnswerFromList(instances_list,
                                            enable_choose_all=True)
        return instances

    return instances_list


def ChooseOneRemoteInstance(cfg):
    """Get one remote cuttlefish instance.

    Retrieve all remote cuttlefish instances and if there is more than 1 instance
    found, ask user which instance they'd like.

    Args:
        cfg: AcloudConfig object.

    Raises:
        errors.NoInstancesFound: No cuttlefish remote instance found.

    Returns:
        list.Instance() object.
    """
    instances_list = GetCFRemoteInstances(cfg)
    if not instances_list:
        raise errors.NoInstancesFound(
            "Can't find any cuttlefish remote instances, please try "
            "'$acloud create' to create instances")
    if len(instances_list) > 1:
        print("Multiple instances detected, choose any one to proceed:")
        instances = utils.GetAnswerFromList(instances_list,
                                            enable_choose_all=False)
        return instances[0]

    return instances_list[0]

def GetInstancesFromInstanceNames(cfg, instance_names):
    """Get instances from instance names.

    Turn a list of instance names into a list of Instance().

    Args:
        cfg: AcloudConfig object.
        instance_names: list of instance name.

    Returns:
        List of Instance() object.

    Raises:
        errors.NoInstancesFound: No instances found.
    """
    instance_list = []
    full_list_of_instance = GetInstances(cfg)
    for instance_object in full_list_of_instance:
        if instance_object.name in instance_names:
            instance_list.append(instance_object)

    #find the missing instance.
    missing_instances = []
    instance_list_names = [instance_object.name for instance_object in instance_list]
    missing_instances = [
        instance_name for instance_name in instance_names
        if instance_name not in instance_list_names
    ]
    if missing_instances:
        raise errors.NoInstancesFound("Did not find the following instances: %s" %
                                      ' '.join(missing_instances))
    return instance_list


def GetInstanceFromAdbPort(cfg, adb_port):
    """Get instance from adb port.

    Args:
        cfg: AcloudConfig object.
        adb_port: int, adb port of instance.

    Returns:
        List of list.Instance() object.

    Raises:
        errors.NoInstancesFound: No instances found.
    """
    all_instance_info = []
    for instance_object in GetInstances(cfg):
        if instance_object.forwarding_adb_port == adb_port:
            return [instance_object]
        all_instance_info.append(instance_object.fullname)

    # Show devices information to user when user provides wrong adb port.
    if all_instance_info:
        hint_message = ("No instance with adb port %d, available instances:\n%s"
                        % (adb_port, "\n".join(all_instance_info)))
    else:
        hint_message = "No instances to delete."
    raise errors.NoInstancesFound(hint_message)


def GetCFRemoteInstances(cfg):
    """Look for cuttlefish remote instances.

    Args:
        cfg: AcloudConfig object.

    Returns:
        instance_list: List of instance names.
    """
    instances = GetRemoteInstances(cfg)
    return [ins for ins in instances if ins.avd_type == constants.TYPE_CF]


def Run(args):
    """Run list.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    cfg = config.GetAcloudConfig(args)
    instance_list = GetInstances(cfg)
    PrintInstancesDetails(instance_list, args.verbose)
