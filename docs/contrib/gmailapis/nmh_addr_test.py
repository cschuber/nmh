#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""nmh_addr_test.py

Tests for nmh_addr address parser and accessors.

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

David Levine <levinedl@acm.org> 01 jan 2021
"""

from nmh_addr import nmh_addr

def test_get_addresses():
    #### addresses from To: and Bcc:
    assert ['test@example.com'] == \
           nmh_addr.get_addresses('test@example.com\n')
    assert ['< test@example.com >', 'Test2 <test2@example.com>'] == \
           nmh_addr.get_addresses('\n < test@example.com >, Test2 <test2@example.com>\n')
    assert ['"quoted_local"@example.com'] == \
           nmh_addr.get_addresses('"quoted_local"@example.com\n')
    assert ['"Quoted" <quoted_display@example.com>'] == \
           nmh_addr.get_addresses('"Quoted" <quoted_display@example.com>\n')
    assert ['"comma,_"@example.com'] == \
           nmh_addr.get_addresses('"comma,_"@example.com\n')
    assert ['",Commas," <commas_in_display_name@example.com>'] == \
           nmh_addr.get_addresses('",Commas," <commas_in_display_name@example.com>\n')
    assert ['one', 'two@example.com', 'three', 'four@example.com'] == \
           nmh_addr.get_addresses('one, two@example.com, three,   four@example.com')
    assert ['unbracketed@example.com'] == \
           nmh_addr.get_mailboxes(nmh_addr.get_addresses('<unbracketed@example.com>')[0])
    #### Bcc: with no addresses
    assert [] == nmh_addr.get_addresses('    ')
