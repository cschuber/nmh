/* prompter.c -- simple prompting editor front-end
 *
 * This code is Copyright (c) 2002, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include <h/mh.h>
#include <fcntl.h>
#include <h/signals.h>
#include <setjmp.h>

#include <termios.h>

#define	QUOTE '\\'

#ifndef	CKILL
# define CKILL '@'
#endif

#ifndef	CERASE
# define CERASE '#'
#endif

#define PROMPTER_SWITCHES \
    X("erase chr", 0, ERASESW) \
    X("kill chr", 0, KILLSW) \
    X("prepend", 0, PREPSW) \
    X("noprepend", 0, NPREPSW) \
    X("rapid", 0, RAPDSW) \
    X("norapid", 0, NRAPDSW) \
    X("body", -4, BODYSW) \
    X("nobody", -6, NBODYSW) \
    X("doteof", 0, DOTSW) \
    X("nodoteof", 0, NDOTSW) \
    X("version", 0, VERSIONSW) \
    X("help", 0, HELPSW) \

#define X(sw, minchars, id) id,
DEFINE_SWITCH_ENUM(PROMPTER);
#undef X

#define X(sw, minchars, id) { sw, minchars, id },
DEFINE_SWITCH_ARRAY(PROMPTER, switches);
#undef X


static struct termios tio;
#define ERASE tio.c_cc[VERASE]
#define KILL  tio.c_cc[VKILL]
#define INTR  tio.c_cc[VINTR]

static int wtuser = 0;
static int sigint = 0;
static jmp_buf sigenv;

/*
 * prototypes
 */
int getln (char *, int);
static int chrcnv (char *);
static void chrdsp (char *, char);
static void intrser (int);


int
main (int argc, char **argv)
{
    int body = 1, prepend = 1, rapid = 0;
    int doteof = 0, fdi, fdo, i, state;
    char *cp, *drft = NULL, *erasep = NULL;
    char *killp = NULL, name[NAMESZ], field[NMH_BUFSIZ];
    char buffer[BUFSIZ];
    char **arguments, **argp;
    FILE *in, *out;
    char *tmpfil;
    m_getfld_state_t gstate = 0;

    if (nmh_init(argv[0], 2)) { return 1; }

    arguments = getarguments (invo_name, argc, argv, 1);
    argp = arguments;

    while ((cp = *argp++))
	if (*cp == '-') {
	    switch (smatch (++cp, switches)) {
		case AMBIGSW: 
		    ambigsw (cp, switches);
		    done (1);
		case UNKWNSW: 
		    adios (NULL, "-%s unknown", cp);

		case HELPSW: 
		    snprintf (buffer, sizeof(buffer), "%s [switches] file",
			invo_name);
		    print_help (buffer, switches, 1);
		    done (0);
		case VERSIONSW:
		    print_version(invo_name);
		    done (0);

		case ERASESW: 
		    if (!(erasep = *argp++) || *erasep == '-')
			adios (NULL, "missing argument to %s", argp[-2]);
		    continue;
		case KILLSW: 
		    if (!(killp = *argp++) || *killp == '-')
			adios (NULL, "missing argument to %s", argp[-2]);
		    continue;

		case PREPSW: 
		    prepend++;
		    continue;
		case NPREPSW: 
		    prepend = 0;
		    continue;

		case RAPDSW: 
		    rapid++;
		    continue;
		case NRAPDSW: 
		    rapid = 0;
		    continue;

		case BODYSW: 
		    body++;
		    continue;
		case NBODYSW: 
		    body = 0;
		    continue;

		case DOTSW: 
		    doteof++;
		    continue;
		case NDOTSW: 
		    doteof = 0;
		    continue;
	    }
	} else {
	    if (!drft)
		drft = cp;
	}

    if (!drft)
	adios (NULL, "usage: %s [switches] file", invo_name);
    if ((in = fopen (drft, "r")) == NULL)
	adios (drft, "unable to open");

    if ((tmpfil = m_mktemp2(NULL, invo_name, NULL, &out)) == NULL) {
	adios(NULL, "unable to create temporary file in %s", get_temp_dir());
    }

    /*
     * Are we changing the kill or erase character?
     */
    if (killp || erasep) {
	cc_t save_erase, save_kill;

	/* get the current terminal attributes */
	tcgetattr(0, &tio);

	/* save original kill, erase character for later */
	save_kill = KILL;
	save_erase = ERASE;

	/* set new kill, erase character in terminal structure */
	KILL = killp ? chrcnv (killp) : save_kill;
	ERASE = erasep ? chrcnv (erasep) : save_erase;

	/* set the new terminal attributes */
	 tcsetattr(0, TCSADRAIN, &tio);

	/* print out new kill erase characters */
	chrdsp ("erase", ERASE);
	chrdsp (", kill", KILL);
	chrdsp (", intr", INTR);
	putchar ('\n');
	fflush (stdout);

	/*
	 * We set the kill and erase character back to original
	 * setup in terminal structure so we can easily
	 * restore it upon exit.
	 */
	KILL = save_kill;
	ERASE = save_erase;
    }

    sigint = 0;
    SIGNAL2 (SIGINT, intrser);

    /*
     * Loop through the lines of the draft skeleton.
     */
    for (;;) {
	int fieldsz = sizeof field;
	switch (state = m_getfld (&gstate, name, field, &fieldsz, in)) {
	    case FLD: 
	    case FLDPLUS: 
		/*
		 * Check if the value of field contains anything
		 * other than space or tab.
		 */
		for (cp = field; *cp; cp++)
		    if (*cp != ' ' && *cp != '\t')
			break;

		/* If so, just add header line to draft */
		if (*cp++ != '\n' || *cp != 0) {
		    printf ("%s:%s", name, field);
		    fprintf (out, "%s:%s", name, field);
		    while (state == FLDPLUS) {
			fieldsz = sizeof field;
			state = m_getfld (&gstate, name, field, &fieldsz, in);
			fputs(field, stdout);
			fputs(field, out);
		    }
		} else {
		    /* Else, get value of header field */
		    printf ("%s: ", name);
		    fflush (stdout);
		    i = getln (field, sizeof(field));
		    if (i == -1) {
abort:
			if (killp || erasep) {
			    tcsetattr(0, TCSADRAIN, &tio);
			}
			(void) m_unlink (tmpfil);
			done (1);
		    }
		    if (i != 0 || (field[0] != '\n' && field[0] != 0)) {
			fprintf (out, "%s:", name);
			do {
			    if (field[0] != ' ' && field[0] != '\t')
				putc (' ', out);
			    fputs(field, out);
			} while (i == 1
				    && (i = getln (field, sizeof(field))) >= 0);
			if (i == -1)
			    goto abort;
		    }
		}

		continue;

	    case BODY: 
	    case FILEEOF: 
	        if (!body)
	            break;
		fprintf (out, "--------\n");
		if (field[0] == 0 || !prepend)
		    puts("--------");
		if (field[0]) {
		    if (prepend && body) {
			printf ("\n--------Enter initial text\n\n");
			fflush (stdout);
			for (;;) {
			    getln (buffer, sizeof(buffer));
			    if (doteof && buffer[0] == '.' && buffer[1] == '\n')
				break;
			    if (buffer[0] == 0)
				break;
			    fputs(buffer, out);
			}
		    }

		    do {
			fputs(field, out);
			if (!rapid && !sigint)
			    fputs(field, stdout);
		    } while (state == BODY &&
			    (fieldsz = sizeof field,
			     state = m_getfld (&gstate, name, field, &fieldsz, in)));
		    if (prepend || !body)
			break;
		    else
			printf ("\n--------Enter additional text\n\n");
		}

		fflush (stdout);
		for (;;) {
		    getln (field, sizeof(field));
		    if (doteof && field[0] == '.' && field[1] == '\n')
			break;
		    if (field[0] == 0)
			break;
		    fputs(field, out);
		}
		break;

	    default: 
		adios (NULL, "skeleton is poorly formatted");
	}
	break;
    }
    m_getfld_state_destroy (&gstate);

    if (body)
	puts("--------");

    fflush (stdout);
    fclose (in);
    fclose (out);
    SIGNAL (SIGINT, SIG_IGN);

    if (killp || erasep) {
	 tcsetattr(0, TCSADRAIN, &tio);
    }

    if ((fdi = open (tmpfil, O_RDONLY)) == NOTOK)
	adios (tmpfil, "unable to re-open");
    if ((fdo = creat (drft, m_gmprot ())) == NOTOK)
	adios (drft, "unable to write");
    cpydata (fdi, fdo, tmpfil, drft);
    close (fdi);
    close (fdo);
    (void) m_unlink (tmpfil);

    context_save ();	/* save the context file */
    done (0);
    return 1;
}


int
getln (char *buffer, int n)
{
    int c;
    char *cp;
    static int quoting = 0;

    *buffer = 0;

    switch (setjmp (sigenv)) {
	case OK: 
	    wtuser = 1;
	    break;

	case DONE: 
	    wtuser = 0;
	    return 0;

	default: 
	    wtuser = 0;
	    return NOTOK;
    }

    cp = buffer;
    *cp = 0;

    for (;;) {
	switch (c = getchar ()) {
	    case EOF: 
		quoting = 0;
		clearerr (stdin);
		longjmp (sigenv, DONE);

	    case '\n': 
		if (quoting) {
		    *(cp - 1) = c;
		    quoting = 0;
		    wtuser = 0;
		    return 1;
		}
		*cp++ = c;
		*cp = 0;
		wtuser = 0;
		return 0;

	    default: 
		if (c == QUOTE) {
		    quoting = 1;
		} else {
		    quoting = 0;
		}
		if (cp < buffer + n)
		    *cp++ = c;
		*cp = 0;
	}
    }
}


static void
intrser (int i)
{
    NMH_UNUSED (i);

    if (wtuser)
	longjmp (sigenv, NOTOK);
    sigint++;
}


static int
chrcnv (char *cp)
{
    return (*cp != QUOTE ? *cp : m_atoi (++cp));
}


static void
chrdsp (char *s, char c)
{
    printf ("%s ", s);
    if (c < ' ' || c == 0177)
	printf ("^%c", c ^ 0100);
    else
	printf ("%c", c);
}
