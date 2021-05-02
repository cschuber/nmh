#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""ginc.py

Retrieves mail from user's Gmail inbox.  Assumes that messages are UTF-8
encoded.  Obey's rcvstore behavior for updating Unseen-Sequence, which may
be controlled by the user's profile.

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

Prerequisite:  the user must run the glogin.py script, once,
to login to the Gmail service and acquire the necessary credentials.

Run tests with:  pytest [-v[v]]
Show docs with:  pydoc ./<this filename>

See nmh_gmailapi.py for documentation references.

David Levine <levinedl@acm.org> 28 feb 2021
"""

from nmh_gmailapi import OAuthConfig, get_service
from nmh_gmailapi import InvalidInvocation, UnableToRetrieveOAuthCredentials
from argparse import ArgumentParser, SUPPRESS
from base64 import urlsafe_b64decode
from collections import defaultdict
from subprocess import CalledProcessError, check_output, DEVNULL, Popen, PIPE, run, STDOUT
import os.path, sys


def ginc(argv):
    """Authenticate, then retrieve Gmail messages from inbox.

    argv -- program argument vector
    """
    #### Insert any switches from profile before command line arguments.
    ginc_profile_entry = get_ginc_profile_entry()
    arglist = [argv[0]] + ginc_profile_entry + argv[1:]
    try:
        config, folder, user, all, disposition, delivery, snoop = parse_args(arglist)
    except InvalidInvocation as err:
        print(err, file=sys.stderr)
        return 2
    progname = config.progname()

    #### Authenticate with Google services.
    try:
        service = get_service(config, user, ['readonly'] if disposition == 'keep' else ['modify'])
    except UnableToRetrieveOAuthCredentials as err:
        print('{}: {}'.format(progname, err), file=sys.stderr)
        return 1
    except Exception as err:
        print('{}: {}'.format(progname, type(err)), file=sys.stderr)
        return 1
    try:
        count = retrieve_messages(progname, service, folder, all, disposition, delivery, snoop)
        if count == 0:
            return 0
    except Exception as err:
        print('{}: {}, message retrieval failed'.format(progname, err), file=sys.stderr)
        return 1
    #### If using rcvstore (the default), show the newly incorporated messages.
    if delivery == rcvstore_path(progname):
        scan(progname, folder, count)


def retrieve_messages(progname, service, folder, all, disposition, delivery, snoop):
    """Retrieves messages from inbox and returns their count.

    progname -- name of this program
    service -- authorized Gmail API service instance
    folder -- the mailbox to which messsage is to be delivered
    all -- whether to retrieve only unread (default) or all messages
    disposition -- 'delete', 'mark', or 'keep'
    delivery -- program used to deliver the message
    snoop -- flag to advise user of progress
    raises CalledProcessError, Exception
    """
    #### Get dict of messages to retrieve.
    messages_to_get = get_messages(service, all)
    if snoop:
        print("retrieve messages:", messages_to_get)
    messages = messages_to_get.get('messages')
    if not messages:
        return 0
    #### Retrieve all of the messages, ordering by internalDate.
    retrieved_messages = defaultdict(list)
    for message in messages:
        response = get_message(service, message.get('id'))
        if response:
            retrieved_messages[response.get('internalDate')].append(response)
            if snoop:
                print(response.get('snippet')[:40], response.get('internalDate'), response.get('labelIds'))
    #### Then deliver each message.
    first_message = True
    count = 0
    for timestamp, messages in sorted(retrieved_messages.items()):
        for message in messages:
            if deliver_message(progname, delivery, folder, message):
                count = count + 1
                if disposition == 'delete':
                    delete_message(service, message.get('id'))
                elif disposition == 'mark':
                    mark_message_read(service, message.get('id'))
                if first_message and delivery == rcvstore_path(progname):
                    set_folder_and_cur(progname, folder)
                first_message = False
    return count


def deliver_message(progname, delivery, folder, message):
    """Deliver a single message and return whether successful.

    progname -- name of this program
    delivery -- program used to deliver the message
    folder -- the mailbox to which messsage is to be delivered
    message -- the message to deliver
    raises CalledProcessError
    """
    delivered = False
    if message:
        decoded_message = decode_message(message.get('raw'))
        try:
            args = [delivery]
            if delivery == rcvstore_path(progname):
                args.append('+' + folder)
            p = Popen(args, stdout=PIPE, stdin=PIPE, stderr=PIPE)
            p.communicate(input=decoded_message)[0]
        except CalledProcessError:
            print('{}: {} failed'.format(progname, delivery), file=sys.stderr)
            raise
        delivered = True
    return delivered


def decode_message(message):
    """Decodes a base64url-encoded message and removes trailing carriage
    returns.  Assumes UTF-8 encoding.

    message -- the encoded message
    """
    decoded_message = urlsafe_b64decode(message)
    #### Strip \r from each line.
    return ('\n'.join([line for line in decoded_message.decode().splitlines()])+'\n').encode()


def get_ginc_profile_entry():
    """Returns any profile entry for ginc as list.
    """
    try:
        return check_output(['mhparam', 'ginc']).decode().split()
    except CalledProcessError:
        return []


def rcvstore_path(progname):
    """Returns full path to rcvstore(1).

    progname -- name of this program
    raises CalledProcessError
    """
    try:
        libexecdir = check_output(['mhparam', 'libexecdir']).decode().rstrip()
        return os.path.join(libexecdir, 'rcvstore')
    except CalledProcessError:
        print('{}: mhparam(1) failed'.format(progname), file=sys.stderr)
        raise


def inbox_name():
    """Returns Inbox profile component, or if none, 'inbox'.
    """
    try:
        inbox = check_output(['mhparam', 'Inbox']).decode().rstrip()
        return inbox
    except CalledProcessError:
        return 'inbox'


def set_folder_and_cur(progname, folder):
    """Set current folder to folder and set cur message to latest one.
       inc sets the current folder and sets the current message to the
       first that is incorporated.  rcvstore does not, so we do it manually.

    progname -- name of this program
    folder -- the mailbox to which messsage was delivered
    raises CalledProcessError
    """
    try:
        run(['folder', '+' + folder, 'last'], stdout=DEVNULL)
    except CalledProcessError:
        print('{}: folder(1) failed on {}'.format(progname, folder), file=sys.stderr)
        raise


def scan(progname, folder, count):
    """Displays scan line for the message(s) that just delivered.

    progname -- name of this program
    folder -- the mailbox to which messsage was delivered
    count -- number of messages delivered
    raises CalledProcessError
    """
    try:
        print(check_output(['scan', '+' + folder, 'last:' + str(count)]).decode(), end='')
    except CalledProcessError:
        print('{}: scan(1) failed'.format(progname), file=sys.stderr)
        raise


def get_messages(service, all):
    """Returns messages as dict.

    service -- authorized Gmail API service instance
    all -- whether to retrieve only unread (default) or all messages
    """
    query = 'label:inbox'
    if not all:
        query = query + ' is:unread'
    return service.users().messages().list(userId='me', q=query).execute()


def get_message(service, id):
    """Retrieves and returns a single Message.

    service -- authorized Gmail API service instance
    id -- the Message ID
    """
    return service.users().messages().get(userId='me', id=id, format='raw').execute()


def mark_message_read(service, message_id):
    """Mark message as read by removing UNREAD label.

    id -- the message to mark
    """
    return service.users().messages().modify(userId='me', id=message_id, \
                                             body={'removeLabelIds' : ['UNREAD']}).execute()


def delete_message(service, message_id):
    """Moves message to trash.

    id -- the message to move to trash
    """
    return service.users().messages().trash(userId='me', id=message_id).execute()


def parse_args(arglist):
    """Parse command line arguments, returning OAuthConfig, folder, user,
    all flag, disposition, delivery program, and snoop flag.

    arglist -- list of arguments from profile and command line
    raises InvalidInvocation
    Exits the program with status 0 if -version or -help is specified.
    """
    progname = os.path.basename(arglist[0])
    usage = progname + """ [switches] -user username | -version | -help
  switches are:
  +folder
  -all (instead of just unread inbox messages)
  -disposition delete|mark|keep
  -delivery program
  -snoop
  -user username
  -version
  -help

+folder is ignored if the delivery program is not rcvstore.
-disposition delete (default) moves each message to Gmail trash.
-disposition mark marks each message as read.
The delivery program defaults to rcvstore.
"""
    parser = ArgumentParser(usage=usage, add_help=False)
    parser.add_argument('folder', nargs='?', default=None, help=SUPPRESS)
    parser.add_argument('-all', action='store_true', help=SUPPRESS)
    parser.add_argument('-disposition', default='delete', choices={'delete', 'mark', 'keep'},
                        help=SUPPRESS)
    parser.add_argument('-delivery', default=rcvstore_path(progname), help=SUPPRESS)
    parser.add_argument('-snoop', action='store_true', help=SUPPRESS)
    parser.add_argument('-user', nargs=1, help=SUPPRESS)
    parser.add_argument('-version', action='version', version='%(prog)s -- 0.9', help=SUPPRESS)
    parser.add_argument('-help', action='help', help=SUPPRESS)
    args = parser.parse_args(arglist[1:])

    folder = inbox_name()
    if args.folder:
        if args.folder[0] == '+':
            folder = args.folder[1:]
        else:
            message = 'Usage: {}{}: error: unrecognized argument: {}'.format(usage, progname, args.folder)
            raise InvalidInvocation(message)
    if not args.user:
        raise InvalidInvocation('Usage: {}{}: error: missing -user switch'.format(usage, progname))
    return OAuthConfig(progname, False, args.user[0], None, None, None, None, None), \
        folder, args.user[0], args.all, args.disposition, args.delivery, args.snoop


if __name__ == '__main__':
    sys.exit(ginc(sys.argv))
