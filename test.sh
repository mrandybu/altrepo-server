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
