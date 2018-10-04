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
r"""Custom Exceptions for acloud."""


class SetupError(Exception):
    """Base Setup cmd exception."""


class PackageInstallError(SetupError):
    """Error related to package installation."""


class RequiredPackageNotInstalledError(SetupError):
    """Error related to required package not installed."""


class UnableToLocatePkgOnRepositoryError(SetupError):
    """Error related to unable to locate package."""


class NotSupportedPlatformError(SetupError):
    """Error related to user using a not supported os."""


class ParseBucketRegionError(SetupError):
    """Raised when parsing bucket information without region information."""


class CreateError(Exception):
    """Base Create cmd exception."""


class GetEnvAndroidProductOutError(CreateError):
    """Can't get client environment ANDROID_PRODUCT_OUT."""


class CheckPathError(CreateError):
    """Path does not exist."""


class UnsupportedInstanceImageType(CreateError):
    """Unsupported create action for given instance/image type."""


class GetBuildIDError(CreateError):
    """Can't get build id from Android Build."""


class GetBranchFromRepoInfoError(CreateError):
    """Can't get branch information from output of #'repo info'."""


class NotSupportedHWPropertyError(CreateError):
    """An error to wrap a non-supported property issue."""


class MalformedDictStringError(CreateError):
    """Error related to unable to convert string to dict."""


class InvalidHWPropertyError(CreateError):
    """An error to wrap a malformed hw property issue."""


class GetLocalImageError(CreateError):
    """Can't find the local image."""


class GetCvdLocalHostPackageError(CreateError):
    """Can't find the lost host package."""
