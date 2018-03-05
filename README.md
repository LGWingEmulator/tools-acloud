The Cloud Android Driver Binaries (namely, acloud) in this project provide the
standard APIs to access and control Cloud Android devices (i.e., Android Virtual
Devices on Google Compute Engine) instantiated by using the Android source code

#1. Compilation:

    `$ make acloud` # this produces acloud.zip

#2. Installation:

    `$ pip install -r tools/acloud/pip_requirements.txt out/host/linux-x86/tools/acloud.zip`

#3. Execution:

    `$ acloud <flags>

To run all unit tests:

    `$ tools\acloud\run_tests.sh`
