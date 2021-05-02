#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""nmh_addr.py

Adds alias support to RFC5322 class.

Run tests with:  pytest [-v[v]] nmh_addr_test.py
Show docs with:  pydoc ./<this filename>

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

David Levine <levinedl@acm.org> 01 jan 2021
"""

from RFC5322addr import RFC5322addr as _
import re

class nmh_addr(_):
    #### MH/nmh aliases allow any character except whitespace (HT, LF, VT, FF, CR,
    #### SP), colon, and semicolon.  Practically, comma can be excluded because
    #### it can't be used in an alias in a draft message.  Excluding it allows
    #### parsing of alias lists with aliases separated by commas.
    mh_alias       = r'[^\x09-\x0d\x20,:;]+'
    #### Address or alias.  Allow leading , to easily support the named group.
    addr_alias     = r',?(?P<addr>' + _.mailbox + r'|' + _.group + r'|' + mh_alias + r')'
    addr_alias_pat = re.compile(addr_alias, re.IGNORECASE)

    @staticmethod
    def get_addresses(addresses):
        """Returns list of addresses in a string comprised of addresses and aliases.

        addresses -- the string of addresses and aliases
        """
        addrs = []
        for addr in nmh_addr.addr_alias_pat.finditer(addresses):
            #### There can be leading whitespace because of the first CFWS in
            #### dot_atom, so filter it and any trailing whitespace.
            addrs.append(addr.group('addr').strip())
        return addrs
