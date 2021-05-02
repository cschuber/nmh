#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""RFC5322addr_test.py

Tests for RFC 5322 address parser and accessors.

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

David Levine <levinedl@acm.org> 01 jan 2021
"""

from RFC5322addr import RFC5322addr

def test_get_mailboxes():
    #### addresses from From:
    assert ['test@example.com'] == RFC5322addr.get_mailboxes('test@example.com\n')
    assert ['test@example.com', 'test2@example.com'] == \
           RFC5322addr.get_mailboxes('\n < test@example.com >, Test2 <test2@example.com>\n')
    #### single address from Sender:
    assert ['test@example.com'] == RFC5322addr.get_mailboxes('test@example.com')
    assert ['test@example.com'] == RFC5322addr.get_mailboxes('test@example.com\n')

def test_get_addr_spec():
    assert 'test@example.com' == RFC5322addr.get_addr_spec('test@example.com')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('  test@example.com\n')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('<test@example.com>')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('<  test@example.com  >')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('Display Name <test@example.com>')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('"Display,Name" <test@example.com>')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('"Display.Name" <test@example.com>')
    assert 'test@example.com' == RFC5322addr.get_addr_spec('"Display. Name" <test@example.com>')
    # These require support of obs-phrase:
    # assert 'test@example.com' == RFC5322addr.get_addr_spec('Display.Name <test@example.com>')
    # assert 'test@example.com' == RFC5322addr.get_addr_spec('Display. Name <test@example.com>')
