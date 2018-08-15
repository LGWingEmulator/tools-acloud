#!/bin/bash

function remove_cuttlefish_pkg() {
    echo "uninstalling cuttlefish-common"
    sudo su -c "apt-get purge cuttlefish-common -y && apt-get autoremove -y"
}

function remove_cuttlefish_usergroup() {
    local GROUPS_TO_REMOVE=("kvm" "libvirt" "cvdnetwork")
    echo "remove user from groups: ${GROUPS_TO_REMOVE[@]}"
    for g in ${GROUPS_TO_REMOVE[@]};
    do
        sudo gpasswd -d $USER $g
    done
    su - $USER
}

function purge_cuttlefish(){
   remove_cuttlefish_pkg
   remove_cuttlefish_usergroup
   echo 'purge cuttlefish finish!'
}

purge_cuttlefish