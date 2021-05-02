#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""RFC5322addr.py

RFC 5322 address parser and accessors.

Run tests with:  pytest [-v[v]] RFC5322addr_test.py
Show docs with:  pydoc ./<this filename>

This code is Copyright (c) 2021, by the authors of nmh.
See the COPYRIGHT file in the root directory of the nmh distribution or
http://git.savannah.nongnu.org/cgit/nmh.git/plain/COPYRIGHT
for complete copyright and conditions information.

David Levine <levinedl@acm.org> 01 jan 2021
"""

import re

class RFC5322addr():
    #### RFC 5234 §B.1.  Core Rules
    CR             = r'[\x0d]'
    DQUOTE         = r'[\x22]'
    LF             = r'[\x0a]'
    WSP            = r'[\x09\x20]'
    #### Made the CR optional to support native *nix files.
    CRLF           = r'(' + CR + r'?' + LF + r')'
    VCHAR          = r'[\x21-\x7e]'

    #### RFC 5322 §3.2.1.  Quoted characters
    #### Exclude obs-qp from quoted-pair because it includes most control characters.
    quoted_pair    = r'(\\(' + VCHAR + r'|' + WSP + r'))'

    #### RFC 5322 §3.2.2.  Folding White Space and Comments
    #### Exclude obs-FWS because it allowed a line of just white space in a header field.
    FWS            = r'((' + WSP + r')*' + CRLF + r'?' + WSP + r'+)'
    ctext          = r'[\x21-\x27\x2a-\x5b\x5d-\x7e]'
    #### Broke recursive definition by excluding comment within comment.
    comment        = r'(\(' + FWS + r'?' + r'(' + ctext + r'|' + quoted_pair + r')*' + FWS + r'?\))'
    CFWS           = r'(((' + FWS + r'?' + comment + r')+' + FWS + r'?)|' + FWS + r')'

    #### RFC 5322 §3.2.3.  Atom
    atext          = r"[-!#$%&'*+/\x30-\x39=?\x41-\x5a^_`\x61-\x7a{\|}~]"
    atom           = r'(' + CFWS + r'?' + atext + r'+' + CFWS + r'?' + r')'
    dot_atom_text  = r'(' + atext + r'+' + r'(\.' + atext + r'+)*' + r')'
    dot_atom       = r'(' + CFWS + r'?' + dot_atom_text + CFWS + r'?' + r')'

    #### RFC 5322 §3.2.4.  Quoted strings
    qtext          = r'[\x21\x23-\x5b\x5d-\x7e]'
    qcontent       = r'(' + qtext + r'|' + quoted_pair + r')'
    quoted_string  = r'(' + CFWS + r'?' + DQUOTE + r'(' + FWS + r'?' + qcontent + r')*' + \
                     FWS + r'?' + DQUOTE + CFWS + r'?' + r')'

    #### RFC 5322 §3.2.5.  Miscellaneous tokens
    word           = r'('+ atom + r'|' + quoted_string + r')'
    phrase         = word + '+'

    #### RFC 5322 §3.4.1.  Addr-Spec Specification
    local_part     = r'(' + dot_atom + r'|' + quoted_string + r')'
    dtext          = r'[\x21-\x5a\x5e-\x7e]'
    domain_literal = r'(' + CFWS + r'?\[(' + FWS + r'?' + dtext + r')*' + FWS + r'?\]' + CFWS + r'?)'
    domain         = r'(' + dot_atom + r'|' + domain_literal + r')'
    addr_spec      = r'(' + local_part + r'@' + domain + r')'

    #### RFC 5322 §3.4.  Address Specification
    display_name   = phrase
    angle_addr     = r'(' + CFWS + r'?<' + addr_spec + r'>' + CFWS + r'?)'
    name_addr      = r'((' + display_name + r')?' + angle_addr + r')'
    mailbox        = r'(' + name_addr + r'|' + addr_spec + r')'
    mailbox_list   = r'(' + mailbox + r'(,' + mailbox + r')*)'
    group          = r'(' + display_name + r':(' + mailbox_list + r'|' + CFWS + r')?;' + CFWS + r'?)'
    address        = r'(?P<address>' + mailbox + r'|' + group + r')'
    address_list   = r'(' + address + r'(, ' + address + r')*)'

    #### RFC 5322 §3.6.2.  Originator Fields
    # from_field   = r'From:' + mailbox_list + CRLF
    # sender       = r'Sender:' + mailbox + CRLF

    #### RFC 5322 §3.6.3.  Destination Address Fields
    # "to" also includes Reply-To and Cc to reduce the number of patterns to compile
    # to  = r'(To|Cc|Reply-To):' + address_list + CRLF
    # bcc = r'Bcc:' + r'(' + address_list + r'|(' + CFWS + r')?)' + CRLF

    mailbox_list_pat = re.compile(mailbox_list, re.IGNORECASE)
    addr_pat         = re.compile(address, re.IGNORECASE)

    #### For extracting the addr-spec from a mailbox.  angle_addr above can't
    #### contain a named group because it would appear multiple times in the
    #### address regular expression.  And mailbox above can't contain a named
    #### group, either, because it would appear twice in mailbox_list.
    angle_addr2    = r'(' + CFWS + r'?<(?P<addr_spec>' + addr_spec + r')>' + CFWS + r'?)'
    name_addr2     = r'((' + display_name + r')?' + angle_addr2 + r')'
    mailbox2       = r'(' + name_addr2 + r'|(?P<addr_spec2>' + addr_spec + r'))'
    mailbox2_pat   = re.compile(mailbox2, re.IGNORECASE)

    @staticmethod
    def get_mailboxes(mailboxes):
        """Returns list of addrs in a mailbox_list.

        mailboxes -- the mailbox_list
        """
        addrs = []
        for addr in RFC5322addr.addr_pat.finditer(mailboxes):
            addrs.append(RFC5322addr.get_addr_spec(addr.group('address')))
        return addrs

    @staticmethod
    def get_addr_spec(mailbox):
        """Returns addr-spec part of the mailbox.

        mailbox -- RFC 5322 mailbox
        """
        match = RFC5322addr.mailbox2_pat.match(mailbox)
        if match:
            for addr_type in ('addr_spec', 'addr_spec2'):
                addr_spec = match.group(addr_type)
                if addr_spec:
                    return addr_spec.strip()
        return mailbox
