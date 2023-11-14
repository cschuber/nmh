#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""gpost_test.py

Tests for nmh postproc to post a message using user's Gmail account

Run tests with:  pytest [-v[v]]

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

David Levine <levinedl@acm.org> 01 jan 2021
"""

from gpost import *
import pytest

def test_invalid_switch():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with pytest.raises(SystemExit) as exception:
        gpost(['gpost.py', '-z'])
    assert exception.type == SystemExit
    assert exception.value.code == 2
    assert """usage: gpost.py [switches] file
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
  -saslmech mechanism

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
pytest: error: unrecognized arguments: -z
""" == stderr.getvalue()

def test_nonexistent_message_file():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.TemporaryDirectory() as temp:
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', os.path.join(temp, 'nonexistent')])
    assert re.search(r': message file \'.+\' not found', stderr.getvalue()) and status == 1

def test_dcc_not_supported():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
Dcc: dcc@example.com
From: from@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r'Dcc is not supported\ngpost.py: invalid draft', stderr.getvalue()) and status == 1

def test_from_not_address():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
From: from
To: recipient@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r'From does not have valid address', stderr.getvalue()) and status == 1

def test_envelope_from_not_address():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
Envelope-From: envelope-from
To: recipient@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r'Envelope-From does not have valid address', stderr.getvalue()) and status == 1

def test_sender_not_address():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
From: from@example.com
Sender: sender
To: recipient@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r'Sender does not have valid address', stderr.getvalue()) and status == 1

def test_sender_not_unique():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
From: from@example.com
Sender: sender1@example.com, sender2@example.com
To: recipient@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r'gpost.py: there can be only one unique sender', stderr.getvalue()) and status == 1

def test_whom_without_sender():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
Subject: no sender""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', '-whom', temp.name])
    assert 'whom: message has no From: header' in stderr.getvalue() and status == 1

def test_whom():
    from io import StringIO
    sys.stdout = stdout = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient1@example.com, recipient2@
 example.com
Cc: <cc@example.com>
Bcc: bcc@example.com
From: from@example.com
""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', '-whom', temp.name])
    assert """\
  -- Network Recipients --
  recipient1 at example.com
  recipient2 at example.com
  cc at example.com
  bcc at example.com[BCC]
""" == stdout.getvalue() and status == 0

def test_repeated_header_field():
    from io import StringIO
    sys.stdout = stdout = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient1@example.com
To: recipient2@example.com
To: recipient3@example.com
From: from@example.com
""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', '-whom', temp.name])
    assert """\
  -- Network Recipients --
  recipient1 at example.com
  recipient2 at example.com
  recipient3 at example.com
""" == stdout.getvalue() and status == 0

def test_whom_with_multiple_from_without_sender():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
From: from1@example.com, from2@example.com
""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', '-whom', temp.name])
    assert 'whom: A Sender: or Envelope-From:' in stderr.getvalue() and status == 1

def test_no_from_with_sender():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
Sender: sender@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r': message has no From:', stderr.getvalue()) and status == 1

def test_no_from_with_envelope_from():
    from io import StringIO
    sys.stderr = stderr = StringIO()
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
Envelope-From: envelope_from@example.com""")
        status = gpost(['gpost.py', '-saslmech', 'xoauth2', temp.name])
    assert re.search(r': message has no From:', stderr.getvalue()) and status == 1

def test_envelope_from():
    from io import StringIO
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
From: from@example.com
Envelope-From: envelope_from@example.com""")
        unused, config = parse_args(['gpost.py', '-saslmech', 'xoauth2', temp.name])
        msg_contents, sender, recipients, fccs = prepare_message(config)
    assert """\
To: recipient@example.com
From: from@example.com""" == msg_contents and \
           'envelope_from@example.com' == sender and \
           [['recipient@example.com', '']] == recipients

def test_sender_envelope_from():
    from io import StringIO
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
From: from@example.com
Sender: sender@example.com
Envelope-From: envelope_from@example.com""")
        unused, config = parse_args(['gpost.py', '-saslmech', 'xoauth2', temp.name])
        msg_contents, sender, recipients, fccs = prepare_message(config)
    assert """\
To: recipient@example.com
From: from@example.com""" == msg_contents and \
           'envelope_from@example.com' == sender and \
           [['recipient@example.com', '']] == recipients

def test_angle_bracket_addresses():
    from io import StringIO
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient1@example.com, <recipient2@example.com>
Cc: <cc1@example.com>, cc2@example.com
From: <from@example.com>""")
        unused, config = parse_args(['gpost.py', '-saslmech', 'xoauth2', temp.name])
        msg_contents, sender, recipients, fccs = prepare_message(config)
    assert """\
To: recipient1@example.com, <recipient2@example.com>
Cc: <cc1@example.com>, cc2@example.com
From: <from@example.com>""" == msg_contents and \
           'from@example.com' == sender and \
           [['recipient1@example.com', ''],
            ['<recipient2@example.com>', ''],
            ['<cc1@example.com>', ''],
            ['cc2@example.com', '']] == recipients

def test_bcc():
    from io import StringIO
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
Bcc: bcc@example.com
From: <from@example.com>""")
        unused, config = parse_args(['gpost.py', '-saslmech', 'xoauth2', temp.name])
        msg_contents, sender, recipients, fccs = prepare_message(config)
    assert """\
To: recipient@example.com
Bcc: bcc@example.com
From: <from@example.com>""" == msg_contents and \
           'from@example.com' == sender and \
           [['recipient@example.com', ''],
            ['bcc@example.com', '[BCC]']] == recipients

def test_fcc():
    from io import StringIO
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
Fcc: +outbox
From: <from@example.com>""")
        unused, config = parse_args(['gpost.py', '-saslmech', 'xoauth2', temp.name])
        msg_contents, sender, recipients, fccs = prepare_message(config)
    assert """\
To: recipient@example.com
From: <from@example.com>""" == msg_contents and \
           'from@example.com' == sender and \
           [['recipient@example.com', '']] == recipients and \
           ['outbox'] == fccs

def test_multiple_fcc():
    from io import StringIO
    with tempfile.NamedTemporaryFile(mode='wt') as temp:
        Path(temp.name).write_text("""\
To: recipient@example.com
Fcc: +outbox, +save
FCC: +another
From: <from@example.com>""")
        unused, config = parse_args(['gpost.py', '-saslmech', 'xoauth2', temp.name])
        msg_contents, sender, recipients, fccs = prepare_message(config)
    assert """\
To: recipient@example.com
From: <from@example.com>""" == msg_contents and \
           'from@example.com' == sender and \
           [['recipient@example.com', '']] == recipients and \
           ['outbox', 'save', 'another'] == fccs
