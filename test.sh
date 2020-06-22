#!/bin/bash
SERVER=http://127.0.0.1:5000

BASEQUERY="curl -s -k $SERVER/"

echo "check package info"

# base package info
runtest "package_info?name=glibc"
runtest "package_info?name=glibc&branch=sisyphus"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64&source=false"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64&source=true"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64&source=true"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64&source=true&full=true"
# package was exists but not for x86_64
runtest "package_info?name=startup&branch=sisyphus&source=false&arch=x86_64&full=true"
# all packages by packager_email
runtest "package_info?packager_email=ldv@altlinux.org"
# package by sha1
runtest "package_info?sha1=53ddac04bd35f566a818e020d59b1bcb2e58bbe9"


# misconflict_packages
# syslinux has unresolved file conflict with syslinux1
runtest "misconflict_packages?pkg_ls=glibc,syslinux&branch=sisyphus"
# big task
runtest "misconflict_packages?task=247371"
runtest "misconflict_packages?task=239398"

# package by file
runtest "package_by_file?file='/usr/bin/firefox'&branch=sisyphus"
runtest "package_by_file?file='/usr/bin/firefox-*'&branch=sisyphus"
runtest "package_by_file?md5=a3de87766009c22b59399e6a25573973&branch=p9"

# dependend_packages
runtest "dependent_packages?name=grub-pc&branch=sisyphus"
runtest "dependent_packages?name=ocaml&branch=sisyphus"
runtest "dependent_packages?name=python3&branch=sisyphus"