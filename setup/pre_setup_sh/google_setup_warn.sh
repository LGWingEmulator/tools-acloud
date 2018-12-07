#!/bin/bash

ACLOUD_PREBUILT_PROJECT_DIR=$ANDROID_BUILD_TOP/prebuilts/asuite
ACLOUD_CONFIG_FOLDER=$ANDROID_BUILD_TOP/vendor/google/tools/acloud
GREEN='\033[0;32m'
NC='\033[0m'
RED='\033[0;31m'

# Go to a project we know exists and grab user git config info from there.
if [ ! -d $ACLOUD_PREBUILT_PROJECT_DIR ]; then
    # If this doesn't exist, either it's not a lunch'd env or something weird is going on.
    # Either way, let's stop now.
    exit
fi

# Get the user eMail.
pushd $ACLOUD_PREBUILT_PROJECT_DIR &> /dev/null
USER=$(git config --get user.email)
popd &> /dev/null

# Display disclaimer to googlers if it doesn't look like their env will enable
# streamlined setup.
if [[ $USER == *@google.com ]] && [ ! -d $ACLOUD_CONFIG_FOLDER ]; then
    echo "It looks like you're a googler running acloud for the first time."
    echo -e "Take a look at ${GREEN}go/acloud-googler-setup${NC} before continuing"
    echo "to enable a streamlined setup experience."
    echo -e "Press [enter] to continue with the ${RED}manual setup flow${NC}."
    read
fi
