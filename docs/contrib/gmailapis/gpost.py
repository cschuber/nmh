#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""gpost.py

nmh postproc to post a message using user's Gmail account

The Gmail account is accessed using the argument of the -user switch,
if present, or the sender of the message.  nmh sendfrom is obeyed.

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

Prerequisite:  the user must run the glogin.py script, once,
to login to the Gmail service and acquire the necessary credentials.

The one non-switch command-line argument will be the filename of the message.

Note that Bcc: does work properly.  Gmail will include Bcc headers with
addresses that it knows are the same as the recipient in the recipient's
message.

Messages containing a Dcc: header field are rejected.

Run tests with:  pytest [-v[v]]
Show docs with:  pydoc ./<this filename>

See nmh_gmailapi.py for documentation references.

David Levine <levinedl@acm.org> 01 jan 2021
"""

from nmh_gmailapi import OAuthConfig, get_profile_value, get_service,\
    parse_key_value_list, InvalidInvocation, UnableToRetrieveOAuthCredentials
from pathlib import Path
from nmh_addr import nmh_addr
import argparse, base64, os.path, re, subprocess, sys, tempfile


def gpost(argv):
    """Post a message.  Intended to be used as nmh postproc.

    argv -- program argument vector
    """
    try:
        oauth_config, gpost_config = parse_args(argv)
    except InvalidInvocation as err:
        print('{}: {}'.format(argv[0], err), file=sys.stderr)
        return 2
    progname = oauth_config.progname()

    if gpost_config.dist():
        print('{}: {}'.format(argv[0], 'dist is not yet supported'), file=sys.stderr)
        return 2

    #### Extract the message data that we use.
    try:
        #### recipients are only used with -whom
        msg_contents, sender, recipients, fccs = prepare_message(gpost_config)
    except FileNotFoundError:
        print('{}: message file \'{}\' not found'.format(progname, gpost_config.message_path()),
              file=sys.stderr)
        return 1
    except InvalidDraft as err:
        print('{}: {}'.format(progname, err), file=sys.stderr)
        return 1
    except MissingFrom as err:
        report_missing_from(progname, gpost_config.whom(), err)
        return 1
    except MissingSender as err:
        report_missing_sender(progname, gpost_config.whom(), err)
        return 1
    except (SenderNotAnAddress, SenderNotUnique) as err:
        print('{}: {}'.format(progname, err), file=sys.stderr)
        return 1
    if not sender:
        print('{}: message file \'{}\' has no sender'.format(progname, gpost_config.message_path()),
              file=sys.stderr)
        return 1

    #### whom
    if gpost_config.whom():
        return whom(recipients)

    #### Authenticate with Google services and send the message.
    user = gpost_config.user() if gpost_config.user() else sender
    try:
        service = get_service(oauth_config, user, ['send', 'readonly'])
    except UnableToRetrieveOAuthCredentials as err:
        print('{}: {}'.format(progname, err), file=sys.stderr)
        return 1
    except Exception as err:
        print('{}: {}'.format(progname, type(err)), file=sys.stderr)
        return 1
    encoded_msg = {'raw' : base64.urlsafe_b64encode(msg_contents.encode()).decode()}
    try:
        message = send_message(service, encoded_msg)
        if gpost_config.snoop():
            print('sent message {}'.format(message['id']), file=sys.stderr)
        store_fccs(msg_contents, fccs, get_message_info(service, message['id']))
    except Exception as err:
        print('{}: {}, message not sent'.format(progname, err), file=sys.stderr)
        return 1


def whom(recipients):
    """Report recipients using format of nmh whom(1) and return exit status.

    recipients -- list of recipients
    """
    if len(recipients) == 0:
        print('whom: no addressees', file=sys.stderr)
    else:
        print('  -- Network Recipients --')
        for recipient in recipients:
            print('  {}{}'.format(whom_format(recipient[0]), recipient[1]))
    return 0


def prepare_message(gpost_config):
    """Returns message contents as string, sender, recipients as a list, and Fccs as list.

    gpost_config -- config values object
    raises InvalidDraft, MissingSender, SenderNotAnAddress, SenderNotUnique
    """
    #### Load and parse the message.
    msg_string = Path(gpost_config.message_path()).read_text()

    #### header is the header as a list of header fields.  header_fields is a dictionary
    #### that maps header field names to header field bodies.
    #### For whom -dist, note that whom, replaces the dist draft with the actual message
    #### using distout().  So be sure to look for the Resent- headers.
    header, sender = extract_sender(gpost_config, get_header(msg_string))
    header, fccs = get_fccs(gpost_config.dist(), header)
    header_fields = split_addresses(gpost_config.dist(), parse_key_value_list(header))
    if header_fields.get('dcc'):
        raise InvalidDraft('Dcc is not supported')
    if not gpost_config.dist() and header_fields.get('date'):
        raise InvalidDraft('illegal header line -- Date:, re-format message and retry')
    #### Don't bother adding a Date: field because Gmail will replace it.
    msg_contents, recipients = expand_aliases(gpost_config, msg_string, header, header_fields)
    if gpost_config.snoop():
        print('  -- Message Header --')
        if gpost_config.dist():
            #### Print the entire backup message.  whom replaces the message itself with
            #### what will actually be sent out.  It moves the dist draft to the backup.
            try:
                sbackup = subprocess.check_output(['mhparam', 'sbackup']).decode().rstrip()
            except subprocess.CalledProcessError:
                print('{}: mhparam sbackup failed'.format(progname), file=sys.stderr)
                raise
            path = gpost_config.message_path()
            backup = os.path.dirname(path) + '/' + sbackup + os.path.basename(path)
            print(Path(backup).read_text())
        else:
            try:
                print(msg_contents[:msg_contents.index('\n\n')])
            except ValueError:
                #### No body, just print the entire message (header).
                print(msg_contents)
    return msg_contents, sender, recipients, fccs


def get_header(msg_string):
    """Return msg header as list of lines.

    msg_string -- the message as a string
    """
    header = []
    for line in msg_string.splitlines():
        if line == '':
            break
        if line[0] == ' ' or line[0] == '\t':
            #### continuation (folded) line, append to previous line
            header[-1] = header[-1] + line.lstrip()
        else:
            #### Suppress empty To, Cc, and Bcc.
            if not re.match(r'(to|cc|bcc):\s*$', line.lower()):
                header.append(line)

    return header


def split_addresses(dist, header_fields):
    """For each header field that contains multiple addresses, split the
    addresses in the value list.

    dist -- dist flag
    header_fields -- the dict of header fields
    """
    fields = ('resent-to', 'resent-cc', 'resent-bcc', 'resent-from') if dist else \
        ('to', 'cc', 'bcc', 'from', 'reply-to', 'sender', 'envelope-from')
    for field in fields:
        for addresses in header_fields[field]:
            addr_list = nmh_addr.get_addresses(addresses)
            if len(addr_list) > 1:
                header_fields[field] = addr_list
    return header_fields


def get_fccs(dist, header):
    """Return header with Fcc's, if any, removed and put into a separate list.

    dist -- dist flag
    header -- message header as list
    """
    header_field = r'^Resent-Fcc' if dist else r'^Fcc'
    kv_pat = re.compile(header_field + r':\s*(.*)', re.IGNORECASE)
    fccs = []
    for line in header:
        kv_match = kv_pat.match(line)
        if kv_match:
            ##### Strip leading + from each folder name.
            folders = [folder.strip()[1:] for folder in kv_match.group(1).split(',')]
            for folder in folders:
                fccs.append(folder)

    header = [line for line in header if not re.match(r'fcc:', line.lower())]
    return header, fccs if len(fccs) > 0 else None


def extract_sender(gpost_config, header_in):
    """Return header with Envelope-From and Sender removed, and the sender's mailbox.

    Sender allows authenticating as user if different from message sender.
    gpost_config -- config values object
    header_in -- message header as list
    raises MissingFrom, MissingSender, SenderNotAnAddress, SenderNotUnique
    """
    #### Envelope-From overrides both Sender and From.  Assume that caller
    #### checked for existence of at least one of these header fields.
    #### Envelope-From or Sender are used by nmh but not included in the
    #### outgoing message, so rewrite header without them.
    dist = gpost_config.dist()
    header = []
    envelope_from_pat = re.compile(r'^Envelope-From:\s*(?P<sender>.*)', re.IGNORECASE)
    sender_pat = re.compile((r'^Resent-' if dist else r'^') + r'Sender:\s*(?P<sender>.*)', re.IGNORECASE)
    from_pat = re.compile((r'^Resent-' if dist else r'^') + r'From:\s*(?P<sender>.*)', re.IGNORECASE)
    envelope_from = None
    sender_address = None
    from_address = []
    for line in header_in:
        if not dist:
            match = envelope_from_pat.match(line)
            if match:
                envelope_from = get_sender(match, 'Envelope-From', envelope_from)
                continue
        match = sender_pat.match(line)
        if match:
            sender_address = get_sender(match, 'Sender', sender_address)
            continue
        match = from_pat.match(line)
        if match:
            addr_list = nmh_addr.get_addresses(match.group('sender'))
            if len(addr_list) >= 1:
                from_address.extend([expand_alias(gpost_config, addr).strip() for addr in addr_list])
            else: # len(addr_list) == 0:
                raise SenderNotAnAddress('From does not have valid address')
        #### Retain From: and everything else.
        header.append(line)
    if not from_address:
        raise MissingFrom('message has no From:')
    if envelope_from:
        #### Envelope-From overrides Sender and From.
        sender = envelope_from
    elif sender_address:
        #### Sender overrides From.
        sender = sender_address
    else:
        if len(from_address) == 0:
            raise MissingSender('missing message sender')
        if len(from_address) > 1:
            raise MissingSender('Envelope-From with multiple From:')
        sender = from_address[0]
    return header, get_sendfrom_user(nmh_addr.get_mailboxes(sender)[0])


def get_sendfrom_user(sender):
    """Return user from sendfrom entry of sender, if any, or sender.

    sender -- sender address
    """
    sendfrom = get_profile_value('sendfrom-' + sender)
    if sendfrom:
        match = re.compile(r'.*-user (?P<user>\S+)').match(sendfrom)
        if match:
            return match.group('user')
    return sender


def get_sender(match, field_name, loc):
    """Returns address contained in an Envelope-From, Sender, or From header field.

    match -- match of a pattern with a named 'sender' group
    field_name -- Envelope-From, Sender, or From
    loc -- storage location of the address, to check for duplication
    raises SenderNotAnAddress, SenderNotUnique
    """
    addr_list = nmh_addr.get_mailboxes(match.group('sender'))
    if loc or len(addr_list) > 1:
        raise SenderNotUnique('there should only be one ' + field_name)
    elif len(addr_list) == 1:
        return addr_list[0].strip()
    else: # len(addr_list) == 0
        raise SenderNotAnAddress(field_name + ' does not have valid address')


def expand_aliases(gpost_config, msg_contents, msg_header, header_fields):
    """Expands any email aliases in a message.  Returns message with expanded
    aliases and list of [address, Bcc indicator string]

    gpost_config -- config values object
    msg_contents -- the message as a string
    msg_header -- the message header as a list
    header_fields -- the message header as a dictionary
    """
    recipients = []
    if len(msg_header) == 0:
        return msg_contents, recipients
    try:
        body = msg_contents[msg_contents.index('\n\n') + 2:]
    except ValueError:
        body = None
    dist = gpost_config.dist()

    #### Replace aliases with addresses in the message header.
    for i, line in enumerate(msg_header):
        fields = ('resent-to', 'resent-cc', 'resent-bcc', 'resent-from') if dist else \
            ('to', 'cc', 'bcc', 'from', 'reply-to', 'sender', 'envelope-from')
        for field in fields:
            match = re.match(r'(?P<fieldname>' + field + r'):', line, re.IGNORECASE)
            if not match:
                continue
            #### For folding the addresses in the header field.
            addrs = match.group('fieldname') + ': '
            for addr in split_addresses(gpost_config.dist(), parse_key_value_list([line])).get(field):
                alias = expand_alias(gpost_config, addr)
                if (field == ('resent-to' if dist else 'to')) or \
                   (field == ('resent-cc' if dist else 'cc')) or \
                   (field == ('resent-bcc' if dist else 'bcc')):
                    #### Wrap with [] because whom output does.  It's not a list.
                    recipients.append([alias, '[BCC]' if field == 'bcc' else ''])
                #### Build folded header field.
                start = addrs.rfind('\n ') + 1
                if len(addrs[start:]) + len(alias) > 77:
                    addrs = addrs + '\n ' + alias + ', '
                else:
                    addrs = addrs + alias + ', '
            if addrs.endswith(', '):
                addrs = addrs[:-2]
            msg_header[i] = addrs
    msg_contents = '\n'.join(msg_header) + ('\n\n' + body if body else '')
    return msg_contents, recipients


def expand_alias(gpost_config, addr):
    """Returns addr expanded if it's an alias, or addr itself.

    gpost_config -- config values object
    addr -- the alias or address
    raises subprocess.CalledProcessError
    """
    try:
        ali = ['ali']
        if gpost_config.alias():
            ali.extend(['-alias', gpost_config.alias()])
        ali.append(addr)
        return subprocess.check_output(ali).decode().rstrip()
    except subprocess.CalledProcessError:
        print('{}: \'{}\' failed'.format(sys.argv[0], ' '.join(ali)), file=sys.stderr)
        raise


def whom_format(address):
    """Returns address formatted the way that whom(1) does.

    Removes display name.

    address -- the address to format
    """
    return re.sub(r'.*<(.*)>', r'\1', address.replace('@', ' at '))


def report_missing_from(progname, whom, message):
    """Prints message on stderr for when there is no From: header field.

    progname -- name of this program
    whom -- whether invoked as whom
    message -- message to print, except for whom
    """
    if whom:
        print("""\
whom: message has no From: header
whom: See default components files for examples
whom: re-format message and try again""", file=sys.stderr)
    else:
        print('{}: {}'.format(progname, message), file=sys.stderr)


def report_missing_sender(progname, whom, message):
    """Prints message on stderr when Sender: or Envelopt-From: is messing.

    progname -- name of this program
    whom -- whether invoked as whom
    message -- message to print, except for whom
    """
    if whom:
        print("""\
whom: message has no From: header
whom: A Sender: or Envelope-From: header is required with multiple\nFrom: addresses
whom: re-format message and try again""", file=sys.stderr)
    else:
        print('{}: {}'.format(progname, message), file=sys.stderr)


def send_message(service, message):
    """Sends an email message, returning the sent Message.

    service -- authorized Gmail API service instance
    message --  base64url-encoded message to send
    """
    return service.users().messages().send(userId='me', body=message).execute()


def store_fccs(msg_contents, fccs, sent_header_fields):
    """Store message according to Fcc's.

    msg_contents -- message contents as a string
    fccs -- list of folders to store the Fcc
    sent_header_fields -- Date: and Message-Id header fields, as single string
    """
    if fccs:
        #### Insert the Date: and Message-Id header fields.
        msg_contents = msg_contents.replace('\n\n', '\n' + sent_header_fields + '\n', 1)
        with tempfile.NamedTemporaryFile(mode='wt') as temp:
            temp.write(msg_contents)
            temp.flush()
            for fcc in fccs:
                try:
                    subprocess.check_output(['refile', '-link', '-file', temp.name, '+' + fcc])
                except subprocess.CalledProcessError:
                    print('{}: refile of Fcc to {} failed'.format(sys.argv[0], fcc), file=sys.stderr)


def get_message_info(service, id):
    """Returns the Date: and Message-Id: of a message as a list of header fields.

    service -- authorized Gmail API service instance
    id -- the Message ID
    """
    #### This is why 'readonly' scope was included.
    message = service.users().messages().get(userId='me', id=id, format='metadata',
                                             metadataHeaders=['Date', 'Message-Id']).execute()
    header_fields = ''
    try:
        for header_field in message['payload']['headers']:
            name = header_field['name']
            if name.lower() == 'date' or name.lower() == 'message-id':
                header_fields = header_fields + (name + ': ' + header_field['value'] + '\n')
    except:
        print('Failed to retrieve Date: and Message-Id: from sent message', file=sys.stderr)
    return header_fields


def parse_args(argv):
    """Parse command line arguments, returning OAuthConfig and GpostConfig pair.

    argv -- command line argument list
    raises InvalidInvocation
    Exits the program with status 0 if -version or -help is specified.
    """
    progname = os.path.basename(argv[0])
    usage = progname + """ [switches] file
  switches are:
  -alias aliasfile
  -dist
  -library directory
  -[no]verbose
  -whom
  -version
  -help
  -snoop
  -user username
  -oauthcredfile credential-file
  -oauthclientid client-id
  -oauthclientsecret client-secret
  -oauthtokenendpoint token-endpoint

  The following nmh post(8) switches are ignored:
    -[no]check
    -debug
    -filter filterfile
    -nofilter
    -[no]format
    -[no]mime
    -[no]msgid
    -[no]watch
    -width columns
    -[no]dashstuffing
    -idanno number
    -client host
    -server host
    -[no]sasl
    -saslmech mechanism
    -port server submission port name/number
    -tls
    -initialtls
    -notls
    -[no]certverify
    -fileproc program
    -mhlproc program
    -sendmail program
    -mts smtp|sendmail/smtp|sendmail/pipe
    -credentials legacy|file:filename
    -messageid localname|random
    -authservice auth-service-name
    -oauthauthendpoint authentication-endpoint
    -oauthredirect redirect-uri
    -oauthscope scope
"""
    parser = argparse.ArgumentParser(usage=usage, add_help=False)
    parser.add_argument('-alias', help=argparse.SUPPRESS)
    parser.add_argument('-check', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nocheck', action='store_false', dest='check', help=argparse.SUPPRESS)
    parser.add_argument('-debug', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-dist', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-filter', help=argparse.SUPPRESS)
    parser.add_argument('-nofilter', action='store_const', const=None, dest='filter', help=argparse.SUPPRESS)
    parser.add_argument('-format', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-noformat', action='store_false', dest='format', help=argparse.SUPPRESS)
    parser.add_argument('-library', help=argparse.SUPPRESS)
    parser.add_argument('-mime', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nomime', action='store_false', dest='mime', help=argparse.SUPPRESS)
    parser.add_argument('-msgid', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nomsgid', action='store_false', dest='msgid', help=argparse.SUPPRESS)
    parser.add_argument('-verbose', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-noverbose', action='store_false', dest='verbose', help=argparse.SUPPRESS)
    parser.add_argument('-watch', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nowatch', action='store_false', dest='watch', help=argparse.SUPPRESS)
    parser.add_argument('-whom', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('-width', help=argparse.SUPPRESS)
    parser.add_argument('-version', action='version', version='%(prog)s -- 0.9', help=argparse.SUPPRESS)
    parser.add_argument('-help', action='help', help=argparse.SUPPRESS)
    parser.add_argument('-dashstuffing', action='store_const', const=1, default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nodashstuffing', action='store_const', const=-1, dest='dashstuffing', help=argparse.SUPPRESS)
    parser.add_argument('-idanno', help=argparse.SUPPRESS)
    parser.add_argument('-client', help=argparse.SUPPRESS)
    parser.add_argument('-server', help=argparse.SUPPRESS)
    parser.add_argument('-snoop', action='store_true', help=argparse.SUPPRESS)
    #### Don't support post(8) -partno switch because it no longer appears to be used.
    parser.add_argument('-sasl', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nosasl', action='store_false', dest='sasl', help=argparse.SUPPRESS)
    parser.add_argument('-saslmech', help=argparse.SUPPRESS)
    parser.add_argument('-user', help=argparse.SUPPRESS)
    parser.add_argument('-port', help=argparse.SUPPRESS)
    parser.add_argument('-tls', action='store_const', const=1, help=argparse.SUPPRESS)
    parser.add_argument('-initialtls', action='store_const', const=2, dest='tls', help=argparse.SUPPRESS)
    parser.add_argument('-notls', action='store_const', const=0, dest='tls', help=argparse.SUPPRESS)
    parser.add_argument('-certverify', action='store_true', default=None, help=argparse.SUPPRESS)
    parser.add_argument('-nocertverify', action='store_false', dest='certverify', help=argparse.SUPPRESS)
    parser.add_argument('-fileproc', help=argparse.SUPPRESS)
    parser.add_argument('-mhlproc', help=argparse.SUPPRESS)
    parser.add_argument('-sendmail', help=argparse.SUPPRESS)
    parser.add_argument('-mts', help=argparse.SUPPRESS)
    parser.add_argument('-credentials', help=argparse.SUPPRESS)
    parser.add_argument('-messageid', help=argparse.SUPPRESS)
    parser.add_argument('-authservice', help=argparse.SUPPRESS)
    parser.add_argument('-oauthcredfile', help=argparse.SUPPRESS)
    parser.add_argument('-oauthclientid', help=argparse.SUPPRESS)
    parser.add_argument('-oauthclientsecret', help=argparse.SUPPRESS)
    parser.add_argument('-oauthauthendpoint', help=argparse.SUPPRESS)
    parser.add_argument('-oauthredirect', help=argparse.SUPPRESS)
    parser.add_argument('-oauthtokenendpoint', help=argparse.SUPPRESS)
    parser.add_argument('-oauthscope', help=argparse.SUPPRESS)
    parser.add_argument('file', nargs='?', default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv[1:])
    handle_args(progname, vars(args))

    if args.file == None:
        raise InvalidInvocation('Usage: {}{}: missing file'.format(usage, progname))

    return OAuthConfig(progname, False, None, args.library, args.oauthcredfile,
                       args.oauthclientid, args.oauthclientsecret, args.oauthtokenendpoint), \
           GpostConfig(args.whom, args.file, args.user, args.dist, args.alias, args.snoop)


def handle_args(progname, args):
    """Do what needs to be done with command line arguments.  Includes checking
    for use of any unsupported switch.

    progname -- name of this program
    args -- dict of {switch: value}
    raises InvalidInvocation
    """
    if args.get('verbose'):
        print(str(args))
        for arg in ('check', 'debug', 'filter', 'nofilter', 'format', 'mime', 'msgid',
                    'watch', 'width', 'dashstuffing', 'idanno', 'client', 'server',
                    'sasl', 'saslmech', 'port', 'tls', 'initialtls', 'notls', 'certverify',
                    'fileproc', 'mhlproc', 'sendmail', 'mts', 'credentials', 'messageid',
                    'authservice', 'oauthauthendpoint', 'oauthredirect', 'oauthscope'):
            if args.get(arg) != None:
                print('-{} not supported'.format(arg))


class GpostConfig():
    """Container for relevant configuration values.

    The values come from either the command line or profile.
    """
    def __init__(self, whom, message_path, user, dist, alias, snoop):
        self._whom = whom
        self._message_path = message_path
        self._user = user
        self._dist = dist
        self._alias = resolve_alias_file(alias)
        self._snoop = snoop

    def whom(self):
        """Accessor for whom."""
        return self._whom

    def message_path(self):
        """Accessor for message path."""
        return self._message_path

    def alias(self):
        """Accessor for alias."""
        return self._alias

    def dist(self):
        """Accessor for dist."""
        return self._dist

    def user(self):
        """Accessor for user."""
        return self._user

    def snoop(self):
        """Accessor for snoop."""
        return self._snoop


def resolve_alias_file(alias):
    """Find location of AliasFile.

    alias -- -alias command line switch argument, or None
    """
    if not alias:
        #### No -alias on command line.  Look in profile.
        try:
            alias = subprocess.check_output(['mhparam', 'AliasFile']).decode().rstrip()
        except subprocess.CalledProcessError:
            pass
    if alias:
        #### If not absolute path, try relative to MH Path.
        if alias[1] != '/':
            try:
                path = subprocess.check_output(['mhparam', 'path']).decode().rstrip()
            except subprocess.CalledProcessError:
                print('{}: mhparam path failed'.format(progname), file=sys.stderr)
                raise
        alias = path + '/' + alias
    else:
        #### No -alias on command line or in profile.  Use default.
        try:
            etcdir = subprocess.check_output(['mhparam', 'etcdir']).decode().rstrip()
        except subprocess.CalledProcessError:
            print('{}: mhparam etcdir failed'.format(progname), file=sys.stderr)
            raise
        alias = etcdir + '/MailAliases'


class InvalidDraft(Exception):
    pass

class MissingFrom(Exception):
    pass

class MissingSender(Exception):
    pass

class SenderNotAnAddress(Exception):
    pass

class SenderNotUnique(Exception):
    pass


if __name__ == '__main__':
    sys.exit(gpost(sys.argv))
