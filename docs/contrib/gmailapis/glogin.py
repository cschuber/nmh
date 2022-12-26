#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""glogin.py

Logs in to Gmail service and acquires necessary credentials

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

David Levine <levinedl@acm.org> 14 mar 2021
"""

from nmh_gmailapi import OAuthConfig, get_service, InvalidInvocation, UnableToRetrieveOAuthCredentials
from argparse import ArgumentParser, SUPPRESS
from os.path import basename
import oauthlib, sys


def glogin(argv):
    """Logins in to Gmail API service and stores credentials.

    argv -- program argument vector
    """
    try:
        oauth_config, glogin_config = parse_args(argv)
    except InvalidInvocation as err:
        print('{}: {}'.format(argv[0], err), file=sys.stderr)
        return 2
    try:
        return get_service(oauth_config, None, glogin_config.scopes())
    except UnableToRetrieveOAuthCredentials as err:
        print('{}: {}'.format(oauth_config.progname(), err), file=sys.stderr)
        return 1
    except oauthlib.oauth2.rfc6749.errors.AccessDeniedError:
        print('access denied: this can happen if you cancelled the login')
        return 1


def parse_args(argv):
    """Parse command line arguments, returning an OAuthConfig and an GloginConfig.

    argv -- command line argument list
    raises InvalidInvocation
    Exits the program with status 0 if -version or -help is specified.
    Exits the program with status 2 if usage is not followed.
    """
    progname = basename(argv[0])
    usage = progname + """ [switches] -user address | -version | -help
  switches are:
  -noginc
  -nogincmodify
  -nogpost
  -oauthcredfile path
-noginc excludes authorization for ginc.py
-nogincmodify excludes authorization for ginc.py -disposition delete (the default) and mark
-nogpost excludes authorization for gpost.py
"""
    parser = ArgumentParser(usage=usage, add_help=False)
    parser.add_argument('-user', nargs='?', default=None, help=SUPPRESS)
    parser.add_argument('-version', action='version', version='%(prog)s -- 0.9', help=SUPPRESS)
    parser.add_argument('-help', action='help', help=SUPPRESS)
    parser.add_argument('-oauthcredfile', help=SUPPRESS)
    parser.add_argument('-noginc', action='store_true', help=SUPPRESS)
    parser.add_argument('-nogincmodify', action='store_true', help=SUPPRESS)
    parser.add_argument('-nogpost', action='store_true', help=SUPPRESS)
    args = parser.parse_args(argv[1:])

    if args.user == None:
        raise InvalidInvocation('Usage: {}{}: missing user'.format(usage, progname))

    return OAuthConfig(progname, True, args.user, None, args.oauthcredfile, None, None, None), \
        GloginConfig(args.noginc, args.nogincmodify, args.nogpost)


class GloginConfig():
    """Container for relevant configuration values.

    The values come the command line.
    """
    def __init__(self, noginc, nogincmodify, nogpost):
        self._noginc = noginc
        self._nogincmodify = nogincmodify
        self._nogpost = nogpost

    def scopes(self):
        """Returns list of scopes from ['modify', 'readonly', 'send']
        """
        scope_list = []
        if not self._noginc and not self._nogincmodify:
            scope_list.append('modify')
        if not self._noginc:
            scope_list.append('readonly')
        if not self._nogpost:
            scope_list.append('send')
        return scope_list


if __name__ == '__main__':
    sys.exit(glogin(sys.argv))
