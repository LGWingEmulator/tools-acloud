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
r"""RemoteImageLocalInstance class.

Create class that is responsible for creating a local instance AVD with a
remote image.
"""
from __future__ import print_function
import logging
import os
import subprocess
import tempfile

from acloud import errors
from acloud.create import local_image_local_instance
from acloud.internal import constants
from acloud.internal.lib import android_build_client
from acloud.internal.lib import auth
from acloud.internal.lib import utils
from acloud.setup import setup_common

# Download remote image variables.
_CVD_HOST_PACKAGE = "cvd-host_package.tar.gz"
_CUTTLEFISH_COMMON_BIN_PATH = "/usr/lib/cuttlefish-common/bin/"
_TEMP_IMAGE_FOLDER = os.path.join(tempfile.gettempdir(),
                                  "acloud_image_artifacts", "cuttlefish")
_CF_IMAGES = ["cache.img", "cmdline", "kernel", "ramdisk.img", "system.img",
              "userdata.img", "vendor.img"]
_BOOT_IMAGE = "boot.img"
UNPACK_BOOTIMG_CMD = "%s -boot_img %s" % (
    os.path.join(_CUTTLEFISH_COMMON_BIN_PATH, "unpack_boot_image.py"),
    "%s -dest %s")
ACL_CMD = "setfacl -m g:libvirt-qemu:rw %s"

ALL_SCOPES = [android_build_client.AndroidBuildClient.SCOPE]

logger = logging.getLogger(__name__)


class RemoteImageLocalInstance(local_image_local_instance.LocalImageLocalInstance):
    """Create class for a remote image local instance AVD.

    RemoteImageLocalInstance just defines logic in downloading the remote image
    artifacts and leverages the existing logic to launch a local instance in
    LocalImageLocalInstance.
    """

    @utils.TimeExecute(function_description="Downloading Android Build image")
    def GetImageArtifactsPath(self, avd_spec):
        """Download the image artifacts and return the paths to them.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.

        Raises:
            errors.NoCuttlefishCommonInstalled: cuttlefish-common doesn't install.

        Returns:
            Tuple of (local image file, launch_cvd package) paths.
        """
        if not setup_common.PackageInstalled("cuttlefish-common"):
            raise errors.NoCuttlefishCommonInstalled(
                "Package [cuttlefish-common] is not installed!\n"
                "Please run 'acloud setup --host' to install.")

        image_dir = self._DownloadAndProcessImageFiles(avd_spec)
        launch_cvd_path = os.path.join(image_dir, "bin", constants.CMD_LAUNCH_CVD)

        return image_dir, launch_cvd_path

    def _DownloadAndProcessImageFiles(self, avd_spec):
        """Download the CF image artifacts and process them.

        Download from the Android Build system, unpack the boot img file,
        and ACL the image files.

        Args:
            avd_spec: AVDSpec object that tells us what we're going to create.

        Returns:
            extract_path: String, path to image folder.
        """
        cfg = avd_spec.cfg
        build_id = avd_spec.remote_image[constants.BUILD_ID]
        build_target = avd_spec.remote_image[constants.BUILD_TARGET]
        extract_path = os.path.join(_TEMP_IMAGE_FOLDER, build_id)
        logger.debug("Extract path: %s", extract_path)
        # TODO(b/117189191): If extract folder exists, check if the files are
        # already downloaded and skip this step if they are.
        if not os.path.exists(extract_path):
            os.makedirs(extract_path)
            self._DownloadRemoteImage(cfg, build_target, build_id, extract_path)
            self._UnpackBootImage(extract_path)
            self._AclCfImageFiles(extract_path)

        return extract_path

    @staticmethod
    def _DownloadRemoteImage(cfg, build_target, build_id, extract_path):
        """Download cuttlefish package and remote image then extract them.

        Args:
            cfg: An AcloudConfig instance.
            build_target: String, the build target, e.g. cf_x86_phone-userdebug.
            build_id: String, Build id, e.g. "2263051", "P2804227"
            extract_path: String, a path include extracted files.
        """
        remote_image = "%s-img-%s.zip" % (build_target.split('-')[0],
                                          build_id)
        artifacts = [_CVD_HOST_PACKAGE, remote_image]

        build_client = android_build_client.AndroidBuildClient(
            auth.CreateCredentials(cfg, ALL_SCOPES))
        for artifact in artifacts:
            with utils.TempDir() as tempdir:
                temp_filename = os.path.join(tempdir, artifact)
                build_client.DownloadArtifact(
                    build_target,
                    build_id,
                    artifact,
                    temp_filename)
                utils.Decompress(temp_filename, extract_path)

    @staticmethod
    def _UnpackBootImage(extract_path):
        """Unpack Boot.img.

        Args:
            extract_path: String, a path include extracted files.

        Raises:
            errors.BootImgDoesNotExist: boot.img doesn't exist.
            errors.UnpackBootImageError: Unpack boot.img fail.
        """
        bootimg_path = os.path.join(extract_path, _BOOT_IMAGE)
        if not os.path.exists(bootimg_path):
            raise errors.BootImgDoesNotExist(
                "%s does not exist in %s" % (_BOOT_IMAGE, bootimg_path))

        logger.info("Start to unpack boot.img.")
        try:
            subprocess.check_call(
                UNPACK_BOOTIMG_CMD % (bootimg_path, extract_path),
                shell=True)
        except subprocess.CalledProcessError as e:
            raise errors.UnpackBootImageError(
                "Failed to unpack boot.img: %s" % str(e))
        logger.info("Unpack boot.img complete!")

    @staticmethod
    def _AclCfImageFiles(extract_path):
        """ACL related files.

        Use setfacl so that libvirt does not lose access to this file if user
        does anything to this file at any point.

        Args:
            extract_path: String, a path include extracted files.

        Raises:
            errors.CheckPathError: Path doesn't exist.
        """
        logger.info("Start to acl files: %s", ",".join(_CF_IMAGES))
        for image in _CF_IMAGES:
            image_path = os.path.join(extract_path, image)
            if not os.path.exists(image_path):
                raise errors.CheckPathError(
                    "Specified file doesn't exist: %s" % image_path)
            subprocess.check_call(ACL_CMD % image_path, shell=True)
        logger.info("ACL files completed!")
