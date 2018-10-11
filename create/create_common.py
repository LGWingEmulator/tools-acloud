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
"""Common code used by acloud create methods/classes."""

from __future__ import print_function

import glob
import logging
import os

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import utils

logger = logging.getLogger(__name__)


def ParseHWPropertyArgs(dict_str, item_separator=",", key_value_separator=":"):
    """Helper function to initialize a dict object from string.

    e.g.
    cpu:2,dpi:240,resolution:1280x800
    -> {"cpu":"2", "dpi":"240", "resolution":"1280x800"}

    Args:
        dict_str: A String to be converted to dict object.
        item_separator: String character to separate items.
        key_value_separator: String character to separate key and value.

    Returns:
        Dict created from key:val pairs in dict_str.

    Raises:
        error.MalformedDictStringError: If dict_str is malformed.
    """
    hw_dict = {}
    if not dict_str:
        return hw_dict

    for item in dict_str.split(item_separator):
        if key_value_separator not in item:
            raise errors.MalformedDictStringError(
                "Expecting ':' in '%s' to make a key-val pair" % item)
        key, value = item.split(key_value_separator)
        if not value or not key:
            raise errors.MalformedDictStringError(
                "Missing key or value in %s, expecting form of 'a:b'" % item)
        hw_dict[key.strip()] = value.strip()

    return hw_dict


def VerifyLocalImageArtifactsExist(local_image_dir):
    """Verify the specifies local image dir.

    Look for the image in the local_image_dir, the image name follows the pattern:

    Remote image: {target product}-img-{build id}.zip,
                  an example would be aosp_cf_x86_phone-img-5046769.zip
    Local built image: {target product}-img-{username}.zip,
                       an example would be aosp_cf_x86_64_phone-img-eng.{username}.zip

    Args:
        local_image_dir: A string to specifies local image dir.

    Return:
        Strings of local image path.

    Raises:
        errors.GetLocalImageError: Can't find local image.
    """
    image_pattern = os.path.join(local_image_dir, "*img*.zip")
    images = glob.glob(image_pattern)
    if not images:
        raise errors.GetLocalImageError("No images matching pattern (%s) in %s" %
                                        (image_pattern, local_image_dir))
    if len(images) > 1:
        print("Multiple images found, please choose 1.")
        image_path = utils.GetAnswerFromList(images)[0]
    else:
        image_path = images[0]
    logger.debug("Local image: %s ", image_path)
    return image_path


def DisplayJobResult(report):
    """Print the details of the devices created.

    -Display created device details from the report instance.
        report example:
            'data': [{'devices':[{'instance_name': 'ins-f6a397-none-53363',
                                  'ip': u'35.234.10.162'}]}]
    -Display error message from report.error.

    Args:
        report: A Report instance.
    """
    for device in report.data.get("devices", []):
        adb_port = device.get("adb_port")
        adb_serial = ""
        if adb_port:
            adb_serial = constants.LOCALHOST_ADB_SERIAL % adb_port
        instance_name = device.get("instance_name")
        instance_ip = device.get("ip")
        # Print out the adb serial with the instance name, otherwise just
        # supply the instance name and ip.
        if adb_serial:
            utils.PrintColorString("Device serial: %s (%s[%s])" %
                                   (adb_serial, instance_name, instance_ip),
                                   utils.TextColors.OKGREEN)
        else:
            utils.PrintColorString("Device details: %s[%s]" %
                                   (instance_name, instance_ip),
                                   utils.TextColors.OKGREEN)

    # TODO(b/117245508): Help user to delete instance if it got created.
    if report.errors:
        error_msg = "\n".join(report.errors)
        utils.PrintColorString("Fail in:\n%s\n" % error_msg,
                               utils.TextColors.FAIL)
