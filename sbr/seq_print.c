/* seq_print.c -- Routines to print sequence information.
 *
 * This code is Copyright (c) 2002, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include "h/mh.h"
#include "seq_getnum.h"
#include "seq_print.h"
#include "error.h"


/*
 * Print the sequence membership for the selected messages, for just
 * the given sequence.
 */
#define CONCISE 1  // turn "8 9 10 11" into "8-11"

int
seq_print_msgs (struct msgs *mp, int i, char *seqname, bool emptyok)
{
    int msgnum, r;
    int found = 0;

    if (i < 0)
	i = seq_getnum (mp, seqname);  /* may not exist */

    /*
     * Special processing for "cur" sequence.  We assume that the
     * "cur" sequence and mp->curmsg are in sync (see seq_add.c).
     * This is returned, even if message doesn't exist or the
     * folder is empty.
     */
    if (!strcmp (current, seqname)) {
	if (mp->curmsg)
	    printf("%s: %d\n", current, mp->curmsg);
        return 1;
    }

    /*
     * Now look for the sequence bit on all selected messages
     */
    if (i >= 0) {
	for (msgnum = mp->lowsel; msgnum <= mp->hghsel; msgnum++) {
	    if (!is_selected (mp, msgnum) || !in_sequence (mp, i, msgnum))
		continue;

	    if (!found) {
		printf("%s%s:", seqname,
			is_seq_private(mp, i) ? " (private)" : "");
		found = 1;
	    }

	    printf(" %d", msgnum);
	    if (CONCISE) {
		r = msgnum;  /* start of range? */
		for (++msgnum; msgnum <= mp->hghsel &&
		    (is_selected (mp, msgnum) && in_sequence (mp, i, msgnum));
			msgnum++)
		    /* spin */ ;

		if (msgnum - r > 1)
		    printf("-%d", msgnum - 1);
	    }
	}
    }
    if (found) {
	printf("\n");
    } else if (emptyok) {
	printf("%s%s: \n", seqname,
		(i == -1) ? "" : (is_seq_private(mp, i) ? " (private)" : ""));
    }

    return 1;
}

#ifdef ARCHIVAL

#include "seq_list.h"

/*
 * Historically, mark(1) only dealt with complete sequences, so
 * seq_print() and seq_printall() could simply walk one (or every)
 * sequence and print its message numbers.  Since mark(1) can now
 * filter on messages, the messages are walked instead, and checked to
 * see if they're members of the sequence being printed.
 */

/*
 * Print all the sequences in a folder
 */
void
seq_printall (struct msgs *mp)
{
    size_t i;
    char *list;

    for (i = 0; i < svector_size (mp->msgattrs); i++) {
	list = seq_list (mp, svector_at (mp->msgattrs, i));
	printf ("%s%s: %s\n", svector_at (mp->msgattrs, i),
	    is_seq_private (mp, i) ? " (private)" : "", FENDNULL(list));
    }
}

/*
 * Print a particular sequence in a folder
 */
void
seq_print (struct msgs *mp, char *seqname, bool emptyok)
{
    int i;
    char *list;

    /* get the index of sequence */
    i = seq_getnum (mp, seqname);

    /* get sequence information */
    list = seq_list (mp, seqname);

    printf ("%s%s: %s\n", seqname,
	(i == -1) ? "" : is_seq_private(mp, i) ? " (private)" : "", FENDNULL(list));
}

#endif // UNUSED
