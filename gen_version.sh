#!/bin/bash
OUTFILE="$1"
if [[ -n $BUILD_NUMBER ]]; then
  echo ${BUILD_NUMBER} > ${OUTFILE}
else
  DATETIME=$(TZ='UTC' date +'%Y.%m.%d')
  echo ${DATETIME}_local_build > ${OUTFILE}
fi
