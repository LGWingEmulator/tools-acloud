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
r"""Delete entry point.

Delete will handle all the logic related to deleting a local/remote instance
of an Android Virtual Device.
"""

from __future__ import print_function
import getpass
import logging
import time

from acloud.internal.lib import auth
from acloud.internal.lib import gcompute_client
from acloud.internal.lib import utils
from acloud.public import config
from acloud.public import device_driver

logger = logging.getLogger(__name__)


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


def _DeleteRemoteInstances(args, del_all_instances=False):
    """Look for remote instances and delete them.

    We're going to query the GCP project for all instances that have the user
    mentioned in the metadata. If we find just one instance, print out the
    details of it and delete it. If we find more than 1, ask the user which one
    they'd like to delete unless del_all_instances is True, then just delete
    them all.

    Args:
        args: Namespace object from argparse.parse_args.
        del_all_instances: Boolean, when more than 1 instance is found,
                           delete them all if True, otherwise prompt user.
    """
    cfg = config.GetAcloudConfig(args)
    instances_to_delete = args.instance_names
    if instances_to_delete is None:
        instances_to_delete = _FindRemoteInstances(cfg, getpass.getuser())
    if instances_to_delete:
        # If the user didn't specify any instances and we find more than 1, ask
        # them what they want to do (unless they specified --all).
        if (args.instance_names is None
                and len(instances_to_delete) > 1
                and not del_all_instances):
            print("Multiple instance detected, choose 1 to delete:")
            instances_to_delete = utils.GetAnswerFromList(
                instances_to_delete, enable_choose_all=True)
        # TODO(b/117474343): We should do a couple extra things here:
        #                    - adb disconnect
        #                    - kill ssh tunnel and ssvnc
        #                    - give details of each instance
        #                    - Give better messaging about delete.
        start = time.time()
        utils.PrintColorString("Deleting %s ..." %
                               ", ".join(instances_to_delete),
                               utils.TextColors.WARNING, end="")
        report = device_driver.DeleteAndroidVirtualDevices(cfg,
                                                           instances_to_delete)
        if report.errors:
            utils.PrintColorString("Fail! (%ds)" % (time.time() - start),
                                   utils.TextColors.FAIL)
            logger.debug("Delete failed: %s", report.errors)
        else:
            utils.PrintColorString("OK! (%ds)" % (time.time() - start),
                                   utils.TextColors.OKGREEN)
        return report
    print("No instances to delete")
    return None


def Run(args):
    """Run delete.

    Args:
        args: Namespace object from argparse.parse_args.
    """
    report = _DeleteRemoteInstances(args, args.all)
    # TODO(b/117474343): Delete local instances.
    return report
