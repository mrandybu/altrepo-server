#!/bin/sh -e
#SERVER="http://127.0.0.1:5000"
SERVER="http://10.88.14.8"

BASEQUERY="curl -s -k $SERVER/"

runtest() {
  URL=$1
  [ -z "$URL" ] && exit 1
  echo -n "Getting $SERVER/$URL"
  start=`date +%s.%N`
  RESULT=`curl -s -k "$SERVER/$URL"`
  end=`date +%s.%N`
  RESULT_COUNT=`echo $RESULT| jq -r ".| length"`
  echo " length: $RESULT_COUNT time: `echo $end - $start|bc -l`"
}

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

# what_depends_src
runtest "what_depends_src?task=239070"
runtest "what_depends_src?name=ocaml&branch=sisyphus"
runtest "what_depends_src?name=curl&branch=sisyphus&deep=2"
runtest "what_depends_src?name=curl&branch=sisyphus&deep=3"
runtest "what_depends_src?name=curl&branch=sisyphus&deep=4"
runtest "what_depends_src?name=curl&branch=sisyphus&deep=5"

runtest "what_depends_src?name=curl&branch=sisyphus&deep=3&finitepkg=true"

runtest "what_depends_src?name=curl&branch=sisyphus&deep=1&leaf=opennebula"

runtest "what_depends_src?name=curl&branch=sisyphus&dptype=binary"
runtest "what_depends_src?name=curl&branch=sisyphus&dptype=source"
runtest "what_depends_src?name=curl&branch=sisyphus&dptype=both"
runtest "what_depends_src?name=curl&branch=sisyphus&dptype=binary&leaf=darktable"
runtest "what_depends_src?name=curl&branch=sisyphus&dptype=binary&reqfilter=systemd"
runtest "what_depends_src?name=curl&branch=sisyphus&dptype=binary&reqfilter_source=python"

# unpackaged dirs
runtest "unpackaged_dirs?pkgr=ldv&pkgset=sisyphus"
runtest "unpackaged_dirs?pkgr=ldv&pkgset=sisyphus&arch=i586"

# compare pkgset's
runtest "repo_compare?pkgset1=p9&pkgset2=sisyphus"
runtest "repo_compare?pkgset1=p8&pkgset2=p9"

# find package in pkgset's
runtest "find_pkgset?task=239070"
runtest "find_pkgset?name=curl"

runtest "build_dependency_set?pkg_ls=curl&branch=sisyphus"
