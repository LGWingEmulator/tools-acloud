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

import logging
import os
import re
import subprocess

from acloud import errors
from acloud.create import create_common
from acloud.internal import constants
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.public import config

# Default values for build target.
_BRANCH_RE = re.compile(r"^Manifest branch: (?P<branch>.+)")
_BUILD_TARGET = "build_target"
_BUILD_BRANCH = "build_branch"
_BUILD_ID = "build_id"
_COMMAND_REPO_INFO = ["repo", "info"]
_DEFAULT_BUILD_BITNESS = "x86"
_DEFAULT_BUILD_TYPE = "userdebug"
_ENV_ANDROID_PRODUCT_OUT = "ANDROID_PRODUCT_OUT"
_ENV_ANDROID_BUILD_TOP = "ANDROID_BUILD_TOP"
_RE_GBSIZE = re.compile(r"^(?P<gb_size>\d+)g$", re.IGNORECASE)
_RE_INT = re.compile(r"^\d+$")
_RE_RES = re.compile(r"^(?P<x_res>\d+)x(?P<y_res>\d+)$")
_X_RES = "x_res"
_Y_RES = "y_res"
_COMMAND_GIT_REMOTE = ["git", "remote"]

# The branch prefix is necessary for the Android Build system to know what we're
# talking about. For instance, on an aosp remote repo in the master branch,
# Android Build will recognize it as aosp-master.
_BRANCH_PREFIX = {"aosp": "aosp-"}
_DEFAULT_BRANCH_PREFIX = "git_"

# The target prefix is needed to help concoct the lunch target name given a
# the branch, avd type and device flavor:
# aosp, cf and phone -> aosp_cf_x86_phone.
_BRANCH_TARGET_PREFIX = {"aosp": "aosp_"}

ALL_SCOPES = [android_build_client.AndroidBuildClient.SCOPE]

logger = logging.getLogger(__name__)


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
        self._report_internal_ip = None
        self._avd_type = None
        self._flavor = None
        self._image_source = None
        self._instance_type = None
        self._kernel_build_id = None
        self._local_image_dir = None
        self._num_of_instances = None
        self._remote_image = None
        self._hw_property = None
        # Create config instance for android_build_client to query build api.
        self._cfg = config.GetAcloudConfig(args)
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
            image_summary = "local image dir"
            image_details = self._local_image_dir
        elif self._image_source == constants.IMAGE_SRC_REMOTE:
            image_summary = "remote image details"
            image_details = self._remote_image
        representation.append(" - %s: %s" % (image_summary, image_details))
        representation.append(" - hw properties: %s" %
                              self._hw_property)
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
        self._ProcessHWPropertyArgs(args)

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

    @staticmethod
    def _ParseHWPropertyStr(hw_property_str):
        """Parse string to dict.

        Args:
            hw_property_str: A hw properties string.

        Returns:
            Dict converted from a string.

        Raises:
            error.MalformedHWPropertyError: If hw_property_str is malformed.
        """
        hw_dict = create_common.ParseHWPropertyArgs(hw_property_str)
        arg_hw_properties = {}
        for key, value in hw_dict.items():
            # Parsing HW properties int to avdspec.
            if key == constants.HW_ALIAS_RESOLUTION:
                match = _RE_RES.match(value)
                if match:
                    arg_hw_properties[_X_RES] = match.group("x_res")
                    arg_hw_properties[_Y_RES] = match.group("y_res")
                else:
                    raise errors.InvalidHWPropertyError(
                        "[%s] is an invalid resolution. Example:1280x800" % value)
            elif key in [constants.HW_ALIAS_MEMORY, constants.HW_ALIAS_DISK]:
                match = _RE_GBSIZE.match(value)
                if match:
                    arg_hw_properties[key] = str(
                        int(match.group("gb_size")) * 1024)
                else:
                    raise errors.InvalidHWPropertyError(
                        "Expected gb size.[%s] is not allowed. Example:4g" % value)
            elif key in [constants.HW_ALIAS_CPUS, constants.HW_ALIAS_DPI]:
                if not _RE_INT.match(value):
                    raise errors.InvalidHWPropertyError(
                        "%s value [%s] is not an integer." % (key, value))
                arg_hw_properties[key] = value

        return arg_hw_properties

    def _ProcessHWPropertyArgs(self, args):
        """Get the HW properties from argparse.parse_args.

        This method will initialize _hw_property in the following
        manner:
        1. Get default hw properties from config.
        2. Override by hw_property args.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        self._hw_property = {}
        self._hw_property = self._ParseHWPropertyStr(self._cfg.hw_property)
        logger.debug("Default hw property for [%s] flavor: %s", self._flavor,
                     self._hw_property)

        if args.hw_property:
            arg_hw_property = self._ParseHWPropertyStr(args.hw_property)
            logger.debug("Use custom hw property: %s", arg_hw_property)
            self._hw_property.update(arg_hw_property)

    def _ProcessMiscArgs(self, args):
        """These args we can take as and don't belong to a group of args.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        self._autoconnect = args.autoconnect
        self._report_internal_ip = args.report_internal_ip
        self._avd_type = args.avd_type
        self._flavor = args.flavor
        self._instance_type = (constants.INSTANCE_TYPE_LOCAL
                               if args.local_instance else
                               constants.INSTANCE_TYPE_REMOTE)
        self._num_of_instances = args.num
        self._kernel_build_id = args.kernel_build_id

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
            self._local_image_dir = args.local_image
        else:
            try:
                self._local_image_dir = os.environ[_ENV_ANDROID_PRODUCT_OUT]
            except KeyError:
                raise errors.GetAndroidBuildEnvVarError(
                    "Could not get environment var: %s\n"
                    "Try to run '#source build/envsetup.sh && lunch <target>'"
                    % _ENV_ANDROID_PRODUCT_OUT
                )

    def _ProcessRemoteBuildArgs(self, args):
        """Get the remote build args.

        Some of the acloud magic happens here, we will infer some of these
        values if the user hasn't specified them.

        Args:
            args: Namespace object from argparse.parse_args.
        """
        self._remote_image = {}
        self._remote_image[_BUILD_BRANCH] = args.branch
        if not self._remote_image[_BUILD_BRANCH]:
            self._remote_image[_BUILD_BRANCH] = self._GetBranchFromRepo()

        self._remote_image[_BUILD_TARGET] = args.build_target
        if not self._remote_image[_BUILD_TARGET]:
            self._remote_image[_BUILD_TARGET] = self._GetBuildTarget(args)

        self._remote_image[_BUILD_ID] = args.build_id
        if not self._remote_image[_BUILD_ID]:
            credentials = auth.CreateCredentials(self._cfg, ALL_SCOPES)
            build_client = android_build_client.AndroidBuildClient(credentials)
            self._remote_image[constants.BUILD_ID] = build_client.GetLKGB(
                self._remote_image[constants.BUILD_TARGET],
                self._remote_image[constants.BUILD_BRANCH])

    @staticmethod
    def _GetGitRemote():
        """Get the remote repo.

        We'll go to a project we know exists (tools/acloud) and grab the git
        remote output from there.

        Returns:
            remote: String, git remote (e.g. "aosp").
        """
        try:
            android_build_top = os.environ[constants.ENV_ANDROID_BUILD_TOP]
        except KeyError:
            raise errors.GetAndroidBuildEnvVarError(
                "Could not get environment var: %s\n"
                "Try to run '#source build/envsetup.sh && lunch <target>'"
                % _ENV_ANDROID_BUILD_TOP
            )

        acloud_project = os.path.join(android_build_top, "tools", "acloud")
        return subprocess.check_output(_COMMAND_GIT_REMOTE,
                                       cwd=acloud_project).strip()

    def _GetBranchFromRepo(self):
        """Get branch information from command "repo info".

        Returns:
            branch: String, git branch name. e.g. "aosp-master"

        Raises:
            errors.GetBranchFromRepoInfoError: Can't get branch from
            output of "repo info".
        """
        repo_output = subprocess.check_output(_COMMAND_REPO_INFO)
        for line in repo_output.splitlines():
            match = _BRANCH_RE.match(line)
            if match:
                branch_prefix = _BRANCH_PREFIX.get(self._GetGitRemote(),
                                                   _DEFAULT_BRANCH_PREFIX)
                return branch_prefix + match.group("branch")
        raise errors.GetBranchFromRepoInfoError(
            "No branch mentioned in repo info output: %s" % repo_output
        )

    def _GetBuildTarget(self, args):
        """Infer build target if user doesn't specified target name.

        Target = {REPO_PREFIX}{avd_type}_{bitness}_{flavor}-
            {DEFAULT_BUILD_TARGET_TYPE}.
        Example target: aosp_cf_x86_phone-userdebug

        Args:
            args: Namespace object from argparse.parse_args.

        Returns:
            build_target: String, name of build target.
        """
        branch = re.split("-|_", self._remote_image[_BUILD_BRANCH])[0]
        return "%s%s_%s_%s-%s" % (
            _BRANCH_TARGET_PREFIX.get(branch, ""),
            constants.AVD_TYPES_MAPPING[args.avd_type],
            _DEFAULT_BUILD_BITNESS, args.flavor,
            _DEFAULT_BUILD_TYPE)

    @property
    def instance_type(self):
        """Return the instance type."""
        return self._instance_type

    @property
    def image_source(self):
        """Return the image type."""
        return self._image_source

    @property
    def hw_property(self):
        """Return the hw_property."""
        return self._hw_property

    @property
    def local_image_dir(self):
        """Return local image dir."""
        return self._local_image_dir

    @property
    def avd_type(self):
        """Return the avd type."""
        return self._avd_type

    @property
    def autoconnect(self):
        """Return autoconnect."""
        return self._autoconnect

    @property
    def remote_image(self):
        """Return the remote image."""
        return self._remote_image

    @property
    def num(self):
        """Return num of instances."""
        return self._num_of_instances

    @property
    def report_internal_ip(self):
        """Return report internal ip."""
        return self._report_internal_ip

    @property
    def kernel_build_id(self):
        """Return kernel build id."""
        return self._kernel_build_id

    @property
    def flavor(self):
        """Return flavor."""
        return self._flavor

    @property
    def cfg(self):
        """Return cfg instance."""
        return self._cfg
