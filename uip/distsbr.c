/* distsbr.c -- routines to do additional "dist-style" processing
 *
 * This code is Copyright (c) 2002, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include "h/mh.h"
#include "sbr/m_backup.h"
#include "sbr/error.h"
#include <fcntl.h>
#include "h/utils.h"
#include "sbr/m_mktemp.h"

static int  hdrfd = NOTOK;
static int  txtfd = NOTOK;

#define	BADHDR	"please re-edit %s to remove the ``%s'' header!"
#define	BADTXT	"please re-edit %s to consist of headers only!"
#define	BADMSG	"please re-edit %s to include a ``Resent-To:''!"
#define	BADRFT	"please re-edit %s and fix that header!"

/*
 * static prototypes
 */
static void ready_msg(char *);

int
distout (char *drft, char *msgnam, char *backup)
{
    int state;
    char *dp, *resent;
    char name[NAMESZ], buffer[NMH_BUFSIZ];
    FILE *ifp, *ofp;
    m_getfld_state_t gstate;

    if (rename (drft, strcpy (backup, m_backup (drft))) == NOTOK)
	adios (backup, "unable to rename %s to",drft);
    if ((ifp = fopen (backup, "r")) == NULL)
	adios (backup, "unable to read");

    if ((ofp = fopen (drft, "w")) == NULL)
	adios (drft, "unable to create temporary file");
    chmod (drft, m_gmprot ());

    ready_msg (msgnam);
    lseek(hdrfd, 0, SEEK_SET); /* msgnam not accurate */
    cpydata (hdrfd, fileno (ofp), msgnam, drft);

    gstate = m_getfld_state_init(ifp);
    for (resent = NULL;;) {
	int buffersz = sizeof buffer;
	switch (state = m_getfld2(&gstate, name, buffer, &buffersz)) {
	    case FLD: 
	    case FLDPLUS: 
		if (uprf (name, "distribute-"))
		    snprintf (name, sizeof(name), "%s%s", "Resent", &name[10]);
		if (uprf (name, "distribution-"))
		    snprintf (name, sizeof(name), "%s%s", "Resent", &name[12]);
		if (!uprf (name, "resent")) {
		    inform(BADHDR, "draft", name);
		    goto leave_bad;
		}
		if (state == FLD)
		    resent = add (":", add (name, resent));
		resent = add (buffer, resent);
		fprintf (ofp, "%s: %s", name, buffer);
		while (state == FLDPLUS) {
		    buffersz = sizeof buffer;
		    state = m_getfld2(&gstate, name, buffer, &buffersz);
		    resent = add (buffer, resent);
		    fputs (buffer, ofp);
		}
		break;

	    case BODY: 
		for (dp = buffer; *dp; dp++)
		    if (!isspace ((unsigned char) *dp)) {
			inform(BADTXT, "draft");
			goto leave_bad;
		    }

	    case FILEEOF: 
		goto process;

	    case LENERR: 
	    case FMTERR: 
		inform(BADRFT, "draft");
	leave_bad: ;
		fclose (ifp);
		fclose (ofp);
		(void) m_unlink (drft);
		if (rename (backup, drft) == NOTOK)
		    adios (drft, "unable to rename %s to", backup);
		return NOTOK;

	    default: 
		die("getfld() returned %d", state);
	}
    }
process: ;
    m_getfld_state_destroy (&gstate);
    fclose (ifp);
    fflush (ofp);

    if (!resent) {
	inform(BADMSG, "draft");
	fclose (ofp);
	(void) m_unlink (drft);
	if (rename (backup, drft) == NOTOK)
	    adios (drft, "unable to rename %s to", backup);
	return NOTOK;
    }
    free (resent);

    if (txtfd != NOTOK) {
	lseek(txtfd, 0, SEEK_SET); /* msgnam not accurate */
	cpydata (txtfd, fileno (ofp), msgnam, drft);
    }

    fclose (ofp);

    return OK;
}


static void
ready_msg (char *msgnam)
{
    int state, out;
    char name[NAMESZ], buffer[NMH_BUFSIZ], tmpfil[BUFSIZ];
    FILE *ifp, *ofp;
    char *cp = NULL;
    m_getfld_state_t gstate;

    if (hdrfd != NOTOK) {
        close (hdrfd);
        hdrfd = NOTOK;
    }
    if (txtfd != NOTOK) {
        close (txtfd);
        txtfd = NOTOK;
    }

    if ((ifp = fopen (msgnam, "r")) == NULL)
	adios (msgnam, "unable to open message");

    cp = m_mktemp2(NULL, "dist", &hdrfd, NULL);
    if (cp == NULL) {
	die("unable to create temporary file in %s", get_temp_dir());
    }
    strncpy(tmpfil, cp, sizeof(tmpfil));
    if ((out = dup (hdrfd)) == NOTOK
	    || (ofp = fdopen (out, "w")) == NULL)
	die("no file descriptors -- you lose big");
    (void) m_unlink (tmpfil);

    gstate = m_getfld_state_init(ifp);
    for (;;) {
	int buffersz = sizeof buffer;
	switch (state = m_getfld2(&gstate, name, buffer, &buffersz)) {
	    case FLD: 
	    case FLDPLUS: 
		if (uprf (name, "resent"))
		    fprintf (ofp, "Prev-");
		fprintf (ofp, "%s: %s", name, buffer);
		while (state == FLDPLUS) {
		    buffersz = sizeof buffer;
		    state = m_getfld2(&gstate, name, buffer, &buffersz);
		    fputs (buffer, ofp);
		}
		break;

	    case BODY: 
		fclose (ofp);

                cp = m_mktemp2(NULL, "dist", &txtfd, NULL);
                if (cp == NULL) {
		    die("unable to create temporary file in %s",
			  get_temp_dir());
                }
                fchmod(txtfd, 0600);
		strncpy (tmpfil, cp, sizeof(tmpfil));
		if ((out = dup (txtfd)) == NOTOK
			|| (ofp = fdopen (out, "w")) == NULL)
		    die("no file descriptors -- you lose big");
		(void) m_unlink (tmpfil);
		fprintf (ofp, "\n%s", buffer);
		while (state == BODY) {
		    buffersz = sizeof buffer;
		    state = m_getfld2(&gstate, name, buffer, &buffersz);
		    fputs (buffer, ofp);
		}
	    case FILEEOF: 
		goto process;

	    case LENERR: 
	    case FMTERR: 
		die("format error in message %s", msgnam);

	    default: 
		die("getfld() returned %d", state);
	}
    }
process: ;
    m_getfld_state_destroy (&gstate);
    fclose (ifp);
    fclose (ofp);
}
