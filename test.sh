#!/bin/bash
SERVER=http://127.0.0.1:5000

BASEQUERY="curl -s -k $SERVER/"

echo "check package info"

# base package
runtest "package_info?name=glibc"
runtest "package_info?name=glibc&branch=sisyphus"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64&source=0"
runtest "package_info?name=glibc&branch=sisyphus&arch=x86_64&source=1"

