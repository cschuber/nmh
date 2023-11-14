#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""nmh_gmailapi.py

Interface to Google services, and some common code, for nmh applications.

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

For instructions on how to install the Gmail API client library for Python:
https://developers.google.com/gmail/api/downloads#python

Documentation of the Gmail service and the API used by this script:
https://developers.google.com/gmail/api/quickstart/python
https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send
https://developers.google.com/gmail/api/guides/sending
https://cloud.google.com/docs/authentication/end-user
https://google-auth.readthedocs.io/en/latest/user-guide.html
  for user credentials via OAuth 2.0
https://developers.google.com/gmail/api/auth/scopes

David Levine <levinedl@acm.org> 01 jan 2021
"""

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from base64 import urlsafe_b64encode
from cryptography.fernet import Fernet
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from re import compile
from subprocess import check_output, CalledProcessError
from string import whitespace
from sys import stderr
from tempfile import NamedTemporaryFile


def get_service(config, sender, scopes):
    """Return gmail service, unless invoked with -login.

    config -- OAuthConfig instance with relevant configuration values
    sender -- message sender
    scopes -- list of scopes from ['modify', 'readonly', 'send']
    raises UnableToRetrieveOAuthCredentials
    """
    progname = config.progname()

    if config.login():
        #### User specified -login, so login to Google OAuth service.
        cred_contents, access, refresh, expire = \
            get_oauth2_creds(progname, config.login_name(), config.cred_file())
        try:
            return login(config, cred_contents, scopes)
        except KeyboardInterrupt:
            raise UnableToRetrieveOAuthCredentials
        return None

    #### Get OAuth credentials.
    cred_contents, creds = get_credentials(config, sender, scopes)

    #### Authenticate with Google services.
    try:
        return authenticate(sender, config.cred_file(), cred_contents, creds)
    except RefreshError:
        raise RefreshFailed


def get_nmh_credential_filename(maildir):
    """Returns name of OAuth credentials file.

    maildir -- user's MH directory
    """
    cred_filename = get_profile_value('oauth-gmail-credential-file')
    if not cred_filename:
        cred_filename = 'oauth-gmail-apis'
    return maildir + '/' + cred_filename


def get_profile_value(component):
    """Return the value of a component from the user's MH profile.

    component -- the profile component
    """
    try:
        return check_output(['mhparam', component]).decode().rstrip()
    except CalledProcessError:
        return None


def get_oauth2_creds(progname, sender, cred_filename):
    """Returns nmh credential file contents and user's nmh OAuth credentials.

    progname -- name of this program
    sender -- sender address
    cred_filename -- nmh credentials filename
    """
    cred_contents = load_nmh_credential_file(progname, cred_filename)
    if not cred_contents:
        return None, None, None, None
    credentials = parse_key_value_list(cred_contents)
    try:
        access = credentials['access-' + sender][0]
        refresh = credentials['refresh-' + sender][0]
        expire = credentials['expire-' + sender][0]
    except IndexError:
        return cred_contents, None, None, None
    return cred_contents, access, refresh, expire


def load_nmh_credential_file(progname, cred_filename):
    """Returns contents of nmh OAuth credential file.

    progname -- name of this program
    cred_filename -- name of nmh credential file
    """
    cred_contents = None
    try:
        cred_contents = Path(cred_filename).read_text().splitlines()
    except FileNotFoundError:
        print('{}: \'{}\' not found, run glogin.py first'.format(progname, cred_filename),
              file=stderr)
    return cred_contents


def login(config, nmh_creds, scopes):
    """Authorizes user accesss to the Gmail service.  Returns 0 on success.

    config -- OAuthConfig instance with relevant configuration values
    nmh_creds -- contents of nmh credential file
    scopes -- list of scopes from ['modify', 'readonly', 'send']
    raises KeyboardInterrupt
    """
    scope = oauth_gmail_scope(scopes)
    json_creds_filename = None
    with NamedTemporaryFile(mode='wt') as temp:
        json_creds_filename = temp.name
        write_json_creds(temp, config.client_id(), config.client_secret())
        flow = InstalledAppFlow.from_client_secrets_file(json_creds_filename, scope)
        try:
            creds = flow.run_local_server(port=0)
        except KeyboardInterrupt:
            print("""\nIf you got a "something went wrong" message, try signing out of
your Google account and then retry this login.""")
            return 1
        update_oauth2_creds(config.login_name(), config.cred_file(), nmh_creds, creds)
        return 0


def oauth_gmail_scope(scopes):
    """Returns the OAuth scopes we use for gmail.

    scopes -- list of scopes from ['modify', 'readonly', 'send']
    """
    gmail_scopes = []
    for scope in scopes:
        gmail_scopes.append('https://www.googleapis.com/auth/gmail.' + scope)
    return gmail_scopes


def update_oauth2_creds(sender, cred_filename, cred_contents, creds):
    """Updates or creates user's nmh OAuth credentials file.

    sender -- sender address
    cred_filename -- name of nmh credential file
    cred_contents -- contents of nmh credential file
    creds -- Credentials
    """
    cred_elements = \
        {compile(r'^(access-{}):'.format(sender)): creds.token,
         compile(r'^(refresh-{}):'.format(sender)): creds.refresh_token,
         compile(r'^(expire-{}):'.format(sender)): datetime.timestamp(creds.expiry)}
    found_sender = False
    if cred_contents:
        for i, line in enumerate(cred_contents):
            for pat, cred_value in cred_elements.items():
                match = pat.match(line)
                if match:
                    cred_contents[i] = '{}: {}'.format(match.group(1), cred_value)
                    found_sender = True
    else:
        cred_contents = []
    if not found_sender:
        cred_contents.append('access-{}: {}'.format(sender, creds.token))
        cred_contents.append('refresh-{}: {}'.format(sender, creds.refresh_token))
        cred_contents.append('expire-{}: {}'.format(sender, datetime.timestamp(creds.expiry)))
    Path(cred_filename).write_text('\n'.join(cred_contents) + '\n')


def write_json_creds(file, client_id, client_secret):
    """Writes a JSON credentials file.

    file -- the file to write
    client_id -- Google installed app client ID
    client_secret -- Google installed app client secret
    """
    json = """\
{{
   "installed" : {{
      "auth_provider_x509_cert_url" : "https://www.googleapis.com/oauth2/v1/certs",
      "auth_uri" : "https://accounts.google.com/o/oauth2/auth",
      "client_id" : "{}",
      "client_secret" : "{}",
      "project_id" : "nmh-apis",
      "redirect_uris" : [
         "urn:ietf:wg:oauth:2.0:oob",
         "http://localhost"
      ],
      "token_uri" : "https://oauth2.googleapis.com/token"
   }}
}}
""".format(client_id, client_secret).translate(str.maketrans('', '', whitespace))
    file.write(json)
    file.flush()
    #### The maketrans(empty, empty, whitespace) call just deletes whitespace.


def parse_key_value_list(lines):
    """Return list of key:value pairs as dict.  Lowercase all keys.  The values
    are lists.

    lines -- list of key:list of values pairs
    """
    kv_pat = compile(r'^([^:]+):\s*(.*)')
    dict = defaultdict(list)
    for line in lines:
        kv_match = kv_pat.match(line)
        if kv_match:
            dict[kv_match.group(1).lower()].append(kv_match.group(2))
    return dict


def get_credentials(config, sender, scopes):
    """Package up the OAuth credentials.

    config -- OAuthConfig instance with relevant configuration values
    sender -- sender address
    scopes -- list of scopes from ['modify', 'readonly', 'send']
    raises UnableToRetrieveOAuthCredentials
    """
    cred_contents, access, refresh, expire = get_oauth2_creds(config.progname(), sender, config.cred_file())
    if not access or not refresh or not expire:
        raise UnableToRetrieveOAuthCredentials
    creds = construct_credentials(config, scopes, access, refresh, expire)
    return cred_contents, creds


def construct_credentials(config, scopes, access, refresh, expire):
    """Constructs and returns Credentials object from pieces that nmh stores.
    See lib/python3.9/site-packages/google/oauth2/credentials.py for undocumented
    expiry argument to Credentials constructor.

    config -- OAuthConfig instance with relevant configuration values
    scopes -- list of scopes from ['modify', 'readonly', 'send']
    access -- Credentials access token
    refresh -- Credentials refresh token
    expire -- Credentials expiry
    """
    return Credentials(
        token = access,
        refresh_token = refresh,
        token_uri = config.client_token_endpoint(),
        client_id = config.client_id(),
        client_secret = config.client_secret(),
        scopes = oauth_gmail_scope(scopes),
        expiry = datetime.fromtimestamp(float(expire)))


def authenticate(sender, cred_filename, cred_contents, creds):
    """Returns Gmail service after authenticates with Gmail API.

    sender -- sender address
    cred_filename -- name of nmh credential file
    cred_contents -- contents of nmh credential file
    creds -- Credentials with which to authenticate
    raises google.auth.exceptions
    """
    if creds and creds.expired and creds.refresh_token and \
       creds.client_id and creds.client_secret:
        creds.refresh(Request())
        update_oauth2_creds(sender, cred_filename, cred_contents, creds)
    elif not creds or creds.expired:
        return None
    return build('gmail', 'v1', credentials=creds)


class OAuthConfig:
    """Container for relevant OAuth configuration values.

    The values come from either the command line or profile.
    """
    def __init__(self, progname, login, login_name, maildir, cred_file,
                 client_id, client_secret, client_token_endpoint):
        self._progname = progname
        self._login = login
        self._login_name = login_name
        self._maildir = maildir
        self._cred_file = cred_file
        self._client_id = client_id
        self._client_secret = client_secret
        self._client_token_endpoint = client_token_endpoint

    def progname(self):
        """Accessor for program name."""
        return self._progname

    def login(self):
        """Accessor for login."""
        return self._login

    def login_name(self):
        """Accessor for login_name."""
        return self._login_name

    def maildir(self):
        """Accessor for maildir."""
        if not self._maildir:
            self._maildir = get_profile_value('path')
            #### If relative path, convert to absolute relative to home directory.
            if not self._maildir[0] == '/':
                self._maildir = str(Path.home()) + '/' + self._maildir
        return self._maildir

    def cred_file(self):
        """Accessor for oauth credentials file."""
        if not self._cred_file:
            self._cred_file = get_nmh_credential_filename(self.maildir())
        return self._cred_file

    def client_id(self):
        """Accessor for client ID."""
        if not self._client_id:
            self._client_id = get_profile_value('oauth-gmail-client_id')
        if not self._client_id:
            self._client_id = _decrypt(b'gAAAAABgSCvvuWnq3kU0qT00H5-V-CQs9K7IehnLfgeAPwoY55rm1qOY8Sx45suUNlZIYBsd23x5W6QAY3dDBaegRKH034gIl2EBeA_lb1uzpgK-pzHt6mGNs9hZnEXgOaVObKPFdFsNyKvPR5ig_uarQy5KWShuQnU7cfxyNToA-vQ7xpOEnHs=')
        return self._client_id

    def client_secret(self):
        """Accessor for client secret."""
        if not self._client_secret:
            self._client_secret = get_profile_value('oauth-gmail-client_secret')
        if not self._client_secret:
            self._client_secret = _decrypt(b'gAAAAABgSCvvvvZzk9TnVex5doDgISYgBk4zpkh1EZOSQJCbehB-4dO96wCnnu26GQXDzQA-d9yH3JB_0dC5335KPsOzCu0RUgiiv7U5GBugMrSf8mF4rko=')
        return self._client_secret

    def client_token_endpoint(self):
        """Accessor for client token endpoint."""
        if not self._client_token_endpoint:
            self._client_token_endpoint = get_profile_value('oauth-gmail-token_endpoint')
        if not self._client_token_endpoint:
            self._client_token_endpoint = 'https://oauth2.googleapis.com/token'
        return self._client_token_endpoint


_key = urlsafe_b64encode(b'*for obfuscation, not security* ')

def _decrypt(token):
    """Decrypt token using key in this file.

    token -- encrypted byte string
    """
    return Fernet(_key).decrypt(token).decode()

def _encrypt(plaintext):
    """Encrypt plaintext using key in this file.

    plaintext -- byte string to be encrypted
    """
    return Fernet(_key).encrypt(plaintext)


class InvalidInvocation(Exception):
    pass

class UnableToRetrieveOAuthCredentials(Exception):
    pass

class RefreshFailed(Exception):
    pass


if __name__ == '__main__':
    # encrypted_client_id = _encrypt(u'not shown'.encode())
    # print(encrypted_client_id)
    # encrypted_client_secret = _encrypt(u'not shown'.encode())
    # print(encrypted_client_secret)
    pass
