/* fmt_addr.c -- format an address field (from fmt_scan)
 *
 * This code is Copyright (c) 2002, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include "h/mh.h"
#include "charstring.h"
#include "fmt_addr.h"
#include "addrsbr.h"
#include "fmt_compile.h"
#include "fmt_scan.h"
#include "utils.h"

static char *buf;		/* our current working buffer  */
static char *bufend;		/* end of working buffer       */
static char *last_dst;		/* buf ptr at end of last call */
static unsigned int bufsiz;	/* current size of buf         */

#define BUFINCR 512		/* how much to expand buf when if fills */

#define CPY(s) { cp = (s); while ((*dst++ = *cp++)) ; --dst; }

/* check if there's enough room in buf for str.  add more mem if needed */
#define CHECKMEM(str) \
	    if ((len = strlen (str)) >= bufend - dst) {\
		int i = dst - buf;\
		int n = last_dst - buf;\
		bufsiz += ((dst + len - bufend) / BUFINCR + 1) * BUFINCR;\
		buf = mh_xrealloc (buf, bufsiz);\
		dst = buf + i;\
		last_dst = buf + n;\
		bufend = buf + bufsiz;\
	    }


/* fmt_scan will call this routine if the user includes the function
 * "(formataddr {component})" in a format string.  "orig" is the
 * original contents of the string register.  "str" is the address
 * string to be formatted and concatenated onto orig.  This routine
 * returns a pointer to the concatenated address string.
 *
 * We try to not do a lot of malloc/copy/free's (which is why we
 * don't call "getcpy") but still place no upper limit on the
 * length of the result string.
 *
 * This routine is placed in a separate library so it can be
 * overridden by particular programs (e.g., "replsbr").
 */

char *
formataddr (char *orig, char *str)
{
    int len;
    bool isgroup;
    char *dst;
    char *cp;
    char *sp;
    struct mailname *mp = NULL;

    /* if we don't have a buffer yet, get one */
    if (bufsiz == 0) {
	buf = mh_xmalloc (BUFINCR);
	last_dst = buf;		/* XXX */
	bufsiz = BUFINCR - 6;  /* leave some slop */
	bufend = buf + bufsiz;
    }
    /*
     * If "orig" points to our buffer we can just pick up where we
     * left off.  Otherwise we have to copy orig into our buffer.
     */
    if (orig == buf)
	dst = last_dst;
    else if (!orig || !*orig) {
	dst = buf;
	*dst = '\0';
    } else {
	dst = last_dst;		/* XXX */
	CHECKMEM (orig);
	CPY (orig);
    }

    /* concatenate all the new addresses onto 'buf' */
    for (isgroup = false; (cp = getname (str)); ) {
	if ((mp = getm (cp, NULL, 0, NULL, 0)) == NULL)
	    continue;

	if (isgroup && (mp->m_gname || !mp->m_ingrp)) {
	    *dst++ = ';';
	    isgroup = false;
	}
	/* if we get here we're going to add an address */
	if (dst != buf) {
	    *dst++ = ',';
	    *dst++ = ' ';
	}
	if (mp->m_gname) {
	    CHECKMEM (mp->m_gname);
	    CPY (mp->m_gname);
	    isgroup = true;
	}
	sp = adrformat (mp);
	CHECKMEM (sp);
	CPY (sp);
	mnfree (mp);
    }

    if (isgroup)
	*dst++ = ';';

    *dst = '\0';
    last_dst = dst;
    return buf;
}

char *
concataddr (char *orig, char *str)
{
    return formataddr(orig, str);
}
