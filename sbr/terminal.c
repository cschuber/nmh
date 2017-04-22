/* terminal.c -- termcap support
 *
 * This code is Copyright (c) 2002, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include <h/mh.h>
#include <h/utils.h>

#include <sys/ioctl.h>

#include <curses.h>
#include <term.h>
#include <termios.h>

#ifdef WINSIZE_IN_PTEM
# include <sys/stream.h>
# include <sys/ptem.h>
#endif

static int initLI = 0;
static int initCO = 0;

static int LI = 40;                /* number of lines                        */
static int CO = 80;                /* number of columns                      */
static char *ti_clear = NULL;      /* terminfo string to clear screen        */
static char *ti_standend = NULL;   /* terminfo string to end standout mode   */
static char *ti_standbegin = NULL; /* terminfo string to begin standout mode */
static int termstatus = 0;	   /* terminfo initialization status         */
static char *termcbuf = NULL;	   /* tputs() output buffer                  */
static char *termcbufp = NULL;	   /* tputs() output buffer pointer          */
static size_t termcbufsz = 0;	   /* Size of termcbuf                       */

static void initialize_terminfo(void);
static int termbytes(TPUTS_PUTC_ARG);

/*
 * Initialize the terminfo library.
 */

static void
initialize_terminfo(void)
{
    int errret, rc;

    if (termstatus)
    	return;

    rc = setupterm(NULL, fileno(stdout), &errret);

    if (rc != 0 || errret != 1) {
    	termstatus = -1;
	return;
    }
    termstatus = 1;

    if (!initCO && (CO = tigetnum ("cols")) <= 0)
	CO = 80;
    if (!initLI && (LI = tigetnum ("lines")) <= 0)
	LI = 24;

    ti_clear = tigetstr ("clear");
    ti_standbegin = tigetstr ("smso");
    ti_standend = tigetstr ("rmso");
}


int
sc_width (void)
{
#ifdef TIOCGWINSZ
    struct winsize win;
    int width;

    if (ioctl (fileno (stderr), TIOCGWINSZ, &win) != NOTOK
	    && (width = win.ws_col) > 0) {
	CO = width;
	initCO++;
    } else
#endif /* TIOCGWINSZ */
	initialize_terminfo();

    return CO;
}


int
sc_length (void)
{
#ifdef TIOCGWINSZ
    struct winsize win;

    if (ioctl (fileno (stderr), TIOCGWINSZ, &win) != NOTOK
	    && (LI = win.ws_row) > 0)
	initLI++;
    else
#endif /* TIOCGWINSZ */
	initialize_terminfo();

    return LI;
}


static int
outc (TPUTS_PUTC_ARG c)
{
    return putchar(c);
}


void
nmh_clear_screen (void)
{
    initialize_terminfo ();

    if (ti_clear)
	tputs (ti_clear, LI, outc);
    else {
	putchar('\f');
    }

    fflush (stdout);
}


/*
 * print in standout mode
 */
int
SOprintf (char *fmt, ...)
{
    va_list ap;

    initialize_terminfo ();
    if (!(ti_standbegin && ti_standend))
	return NOTOK;

    tputs (ti_standbegin, 1, outc);

    va_start(ap, fmt);
    vprintf (fmt, ap);
    va_end(ap);

    tputs (ti_standend, 1, outc);

    return OK;
}

/*
 * Return the specified capability as a string that has already been
 * processed with tputs().
 */

char *
get_term_stringcap(char *capability)
{
    char *parm;

    initialize_terminfo();

    if (termstatus == -1)
    	return NULL;

    termcbufp = termcbuf;

    parm = tigetstr(capability);

    if (parm == (char *) -1 || parm == NULL) {
    	return NULL;
    }

    tputs(parm, 1, termbytes);

    *termcbufp = '\0';

    return termcbuf;
}

/*
 * Return a parameterized terminfo capability
 */

char *
get_term_stringparm(char *capability, long arg1, long arg2)
{
    char *parm;

    initialize_terminfo();

    if (termstatus == -1)
    	return NULL;

    termcbufp = termcbuf;

    parm = tigetstr(capability);

    if (parm == (char *) -1 || parm == NULL) {
    	return NULL;
    }

    parm = tparm(parm, arg1, arg2, 0, 0, 0, 0, 0, 0, 0);

    tputs(parm, 1, termbytes);

    *termcbufp = '\0';

    return termcbuf;
}

/*
 * Return the value of the specified numeric capability
 */

int
get_term_numcap(char *capability)
{
    initialize_terminfo();

    if (termstatus == -1)
    	return -1;

    return tigetnum(capability);
}

/*
 * Store a sequence of characters in our local buffer
 */

static int
termbytes(TPUTS_PUTC_ARG c)
{
    size_t offset;

    /*
     * Bump up the buffer size if we've reached the end (leave room for
     * a trailing NUL)
     */

    if ((offset = termcbufp - termcbuf) - 1 >= termcbufsz) {
        termcbufsz += 64;
    	termcbuf = mh_xrealloc(termcbuf, termcbufsz);
	termcbufp = termcbuf + offset;
    }

    *termcbufp++ = c;

    return 0;
}
