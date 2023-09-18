/* fold.c -- fold a mail header field
 *
 * This code is Copyright (c) 2023, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information. */

#include "h/mh.h"
#include "h/mime.h"
#include "sbr/charstring.h"
#include "fold.h"

void
fold(charstring_t dst, size_t namelen, const char *restrict body)
{
	const char *restrict body_next;
	const char *restrict wsp;
	const char *restrict wsp_next;
	const bool crlf = strchr(body, '\r');
	charstring_clear(dst);
	namelen++;

	while (*body) {
		body_next = strchr(body, '\n');
		if ((unsigned long) (body_next - body) <= MAXTEXTPERLN - namelen) {
			charstring_push_back_chars(dst, body, body_next - body + 1, body_next - body + 1);
			namelen = 0;
			body = body_next + 1;
			continue;
		}
		wsp = body;
		while (namelen == 0 && (*wsp == ' ' || *wsp == '\t')) {
			wsp++;
		}
		wsp = wsp_next = strpbrk(wsp, " \t");

		/* if now whitespace is in the current line just print the curret line as is */
		if (!wsp_next || wsp_next > body_next) {
			charstring_push_back_chars(dst, body, body_next - body + 1, body_next - body + 1);
			namelen = 0;
			body = body_next + 1;
			continue;
		}

		while ((unsigned long)(wsp_next - body) <= MAXTEXTPERLN - namelen) {
			wsp = wsp_next;
			wsp_next = strpbrk(wsp+1, " \t");
			if (!wsp_next) {
				break;
			}
			if (wsp_next > body_next) {
				break;
			}
		}

		charstring_push_back_chars(dst, body, wsp - body, wsp - body);
		if (crlf) {
			charstring_push_back(dst, '\r');
		}
		charstring_push_back(dst, '\n');
		namelen = 0;
		body = wsp;
	}
}
