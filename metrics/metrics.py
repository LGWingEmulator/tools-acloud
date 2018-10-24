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
r"""Acloud metrics functions."""

import logging
import os
import subprocess

from acloud.internal import constants
# pylint: disable=import-error
from asuite import asuite_metrics

_METRICS_URL = 'http://asuite-218222.appspot.com/acloud/metrics'
_VALID_DOMAINS = ["google.com", "android.com"]
_COMMAND_GIT_CONFIG = ["git", "config", "--get", "user.email"]

logger = logging.getLogger(__name__)


def LogUsage():
    """Log acloud run."""
    asuite_metrics.log_event(_METRICS_URL, dummy_key_fallback=False,
                             ldap=_GetLdap())


def _GetLdap():
    """Return string email username for valid domains only, None otherwise."""
    try:
        acloud_project = os.path.join(
            os.environ[constants.ENV_ANDROID_BUILD_TOP], "tools", "acloud")
        email = subprocess.check_output(_COMMAND_GIT_CONFIG,
                                        cwd=acloud_project).strip()
        ldap, domain = email.split("@", 2)
        if domain in _VALID_DOMAINS:
            return ldap
    # pylint: disable=broad-except
    except Exception as e:
        logger.debug("error retrieving email: %s", e)
    return None
