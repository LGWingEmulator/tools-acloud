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
    """Verify local image artifacts exists.

    Look for the image in the local_image_dir and dist dir as backup.

    The image name follows the pattern:
    Remote image: {target product}-img-{build id}.zip,
                  e.g. aosp_cf_x86_phone-img-5046769.zip
    Local built image: {target product}-img-{username}.zip,
                       e.g. aosp_cf_x86_64_phone-img-eng.droid.zip

    Args:
        local_image_dir: A string to specifies local image dir.

    Return:
        Strings of local image path.

    Raises:
        errors.GetLocalImageError: Can't find local image.
    """
    dirs_to_check = [local_image_dir]
    dist_dir = utils.GetDistDir()
    if dist_dir:
        dirs_to_check.append(dist_dir)
    for img_dir in dirs_to_check:
        image_pattern = os.path.join(img_dir, "*img*.zip")
        images = glob.glob(image_pattern)
        if images:
            break
    if not images:
        raise errors.GetLocalImageError("No images found in %s\n"
                                        "(Try building with 'm dist')" %
                                        [local_image_dir, dist_dir])
    if len(images) > 1:
        print("Multiple images found, please choose 1.")
        image_path = utils.GetAnswerFromList(images)[0]
    else:
        image_path = images[0]
    logger.debug("Local image: %s ", image_path)
    return image_path
