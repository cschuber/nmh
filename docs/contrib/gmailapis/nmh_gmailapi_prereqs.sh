#! /bin/sh
#
# Reports the Python packages needed for gpost.py.  If there are any, exits
# with status 1.  If none, prints no output and exits with status 0.
#
# This code is Copyright (c) 2021, by the authors of nmh.
# See the COPYRIGHT file in the root directory of the nmh distribution or
# http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
# for complete copyright and conditions information.
#
# David Levine <levinedl@acm.org> 21 feb 2021

# 1. check for supported Python version
# 2. check for necessary Python packages
# 3. check for installed googleapiclient

count=0

# 1. check for supported Python version
if ! python -c 'import sys; assert sys.version_info >= (3, 6)' 2>/dev/null; then
    count=`expr $count + 1`
    printf "\n$count. %s version is not >= 3.6, later version required.\n" \
           "`python -V`"
fi


# 2. check for necessary Python packages
missing=''
for pkg in cryptography google-auth-httplib2 google-auth-oauthlib; do
    if ! pip show $pkg >/dev/null 2>&1; then
        missing="$missing $pkg"
    fi
done
if [ -n "$missing" ]; then
    count=`expr $count + 1`
    printf "\n$count. Use pip to install$missing\n"
fi


# 3. check for installed googleapiclient
if ! python -c 'import googleapiclient' 2>/dev/null; then
    count=`expr $count + 1`
    printf "\n$count. Install googleapiclient using\n"
    printf 'git clone https://github.com/googleapis/google-api-python-client.git\n'
    printf 'Then install it with pip install google-api-python-client or\n'
    printf 'include it in your PYTHONPATH environment variable.\n'
fi


[ $count = 0 ] && exit 0 || exit 1
