#!/bin/bash 

cwd=$(dirname $0)
sudo=""
if [ ${EUID} ]
then
	sudo=sudo
fi
set -x
${sudo} ${cwd}/config.py
${sudo} ${cwd}/rkt/rkt --local-config=${cwd} $@
