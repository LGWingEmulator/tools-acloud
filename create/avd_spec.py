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
r"""AVDSpec class.

AVDSpec will take in args from the user and be the main data type that will
get passed into the create classes. The inferring magic will happen within
initialization of AVDSpec (like LKGB build id, image branch, etc).
"""

import os

from acloud import errors
from acloud.internal import constants
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.public import config

_BUILD_TARGET = "build_target"
_BUILD_BRANCH = "build_branch"
_BUILD_ID = "build_id"
_ENV_ANDROID_PRODUCT_OUT = "ANDROID_PRODUCT_OUT"

ALL_SCOPES = [android_build_client.AndroidBuildClient.SCOPE]


class AVDSpec(object):
    """Class to store data on the type of AVD to create."""

    def __init__(self, args):
        """Process the args into class vars.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        # Let's define the private class vars here and then process the user
        # args afterwards.
        self._autoconnect = None
        self._avd_type = None
        self._flavor = None
        self._image_source = None
        self._instance_type = None
        self._local_image_path = None
        self._num_of_instances = None
        self._remote_image = None
        # Create config instance for android_build_client to query build api.
        config_mgr = config.AcloudConfigManager(args.config_file)
        self.cfg = config_mgr.Load()

        self._ProcessArgs(args)

    def __repr__(self):
        """Let's make it easy to see what this class is holding."""
        # TODO: I'm pretty sure there's a better way to do this, but I'm not
        # quite sure what that would be.
        representation = []
        representation.append("")
        representation.append(" - instance_type: %s" % self._instance_type)
        representation.append(" - avd type: %s" % self._avd_type)
        representation.append(" - flavor: %s" % self._flavor)
        representation.append(" - autoconnect: %s" % self._autoconnect)
        representation.append(" - num of instances requested: %s" %
                              self._num_of_instances)
        representation.append(" - image source type: %s" %
                              self._image_source)
        image_summary = None
        image_details = None
        if self._image_source == constants.IMAGE_SRC_LOCAL:
            image_summary = "local image path"
            image_details = self._local_image_path
        elif self._image_source == constants.IMAGE_SRC_REMOTE:
            image_summary = "remote image details"
            image_details = self._remote_image
        representation.append(" - %s: %s" % (image_summary, image_details))
        return "\n".join(representation)

    def _ProcessArgs(self, args):
        """Main entry point to process args for the different type of args.

        Split up the arg processing into related areas (image, instance type,
        etc) so that we don't have one huge monolilthic method that does
        everything. It makes it easier to review, write tests, and maintain.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        self._ProcessMiscArgs(args)
        self._ProcessImageArgs(args)

    def _ProcessImageArgs(self, args):
        """ Process Image Args.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        # If user didn't specify --local_image, infer remote image args
        if args.local_image == "":
            self._image_source = constants.IMAGE_SRC_REMOTE
            self._ProcessRemoteBuildArgs(args)
        else:
            self._image_source = constants.IMAGE_SRC_LOCAL
            self._ProcessLocalImageArgs(args)

    def _ProcessMiscArgs(self, args):
        """These args we can take as and don't belong to a group of args.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        self._autoconnect = args.autoconnect
        self._avd_type = args.avd_type
        self._flavor = args.flavor
        self._instance_type = (constants.INSTANCE_TYPE_LOCAL
                               if args.local_instance else
                               constants.INSTANCE_TYPE_REMOTE)
        self._num_of_instances = args.num

    def _ProcessLocalImageArgs(self, args):
        """Get local image path.

        -Specified local_image with no arg: Set $ANDROID_PRODUCT_OUT.
        -Specified local_image with an arg: Set user specified path.

        Args:
            args: Namespace object from argparse.parse_args.

        Raises:
            errors.CreateError: Can't get $ANDROID_PRODUCT_OUT.
        """
        if args.local_image:
            self._local_image_path = args.local_image
        else:
            try:
                self._local_image_path = os.environ[_ENV_ANDROID_PRODUCT_OUT]
            except KeyError as e:
                raise errors.GetEnvAndroidProductOutError(
                    "Could not get environment: %s"
                    "\nTry to run '#. build/envsetup.sh && lunch'"
                    % str(e)
                )

    def _ProcessRemoteBuildArgs(self, args):
        """Get the remote build args.

        Some of the acloud magic happens here, we will infer some of these
        values if the user hasn't specified them.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        # TODO: We need some logic here to determine if we should infer remote
        # build info or not.
        self._remote_image = {}
        if args.build_target:
            self._remote_image[_BUILD_TARGET] = args.build_target
        else:
            # TODO: actually figure out what we want here.
            pass

        if args.branch:
            self._remote_image[_BUILD_BRANCH] = args.branch
        else:
            # TODO: infer from user workspace
            pass

        self._remote_image[_BUILD_ID] = args.build_id
        if not self._remote_image[_BUILD_ID]:
            credentials = auth.CreateCredentials(self.cfg, ALL_SCOPES)
            build_client = android_build_client.AndroidBuildClient(credentials)
            self._remote_image[_BUILD_ID] = build_client.GetLKGB(
                self._remote_image[_BUILD_TARGET],
                self._remote_image[_BUILD_BRANCH])

    @property
    def instance_type(self):
        """Return the instance type."""
        return self._instance_type

    @property
    def image_source(self):
        """Return the image type."""
        return self._image_source
