/* fakesmtp - A fake SMTP server used by the nmh test suite
 *
 * This code is Copyright (c) 2012, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "server.h"

#ifndef min
# define min(a,b) ((a) < (b) ? (a) : (b))
#endif

#define PIDFILE "/tmp/fakesmtp.pid"

#define LINESIZE 1024

enum {
	/* Processing top-level SMTP commands (e.g. EHLO, DATA). */
	SMTP_TOP,

	/* Processing payload of a DATA command. */
	SMTP_DATA,

	/* Looking for the blank line required by XOAUTH2 after 334 response. */
	SMTP_XOAUTH_ERR
};

static ssize_t getsmtp(int, char *);

int
main(int argc, char *argv[])
{
	ssize_t rc;
	int conn, smtp_state;
	FILE *f;
	const char *xoauth = getenv("XOAUTH");
	const char *smtputf8 = getenv("SMTPUTF8");

	if (argc != 3) {
		fprintf(stderr, "Usage: %s output-filename port\n", argv[0]);
		exit(1);
	}

	if (!(f = fopen(argv[1], "w"))) {
		fprintf(stderr, "Unable to open output file \"%s\": %s\n",
			argv[1], strerror(errno));
		exit(1);
	}

	conn = serve(PIDFILE, argv[2]);

	/*
	 * Pretend to be an SMTP server.
	 */

	putcrlf(conn, "220 Not really an ESMTP server");
	smtp_state = SMTP_TOP;

	for (;;) {
		char line[LINESIZE];

		rc = getsmtp(conn, line);

		if (rc == -1)
			break;	/* EOF */

		fwrite(line, rc, 1, f);
		fwrite("\n", 1, 1, f);

		switch (smtp_state) {
		case SMTP_DATA:
			if (strcmp(line, ".") == 0) {
				smtp_state = SMTP_TOP;
				putcrlf(conn, "250 Thanks for the info!");
			}
			continue;
		case SMTP_XOAUTH_ERR:
			smtp_state = SMTP_TOP;
			putcrlf(conn, "535 Not no way, not no how!");
			continue;
		}

		/*
		 * Most commands we ignore and send the same response to.
		 */

		if (strcmp(line, "QUIT") == 0) {
			fclose(f);
			f = NULL;
			putcrlf(conn, "221 Later alligator!");
			close(conn);
			break;
		}
		if (strcmp(line, "DATA") == 0) {
			putcrlf(conn, "354 Go ahead");
			smtp_state = SMTP_DATA;
			continue;
		}
		if (strncmp(line, "EHLO", 4) == 0) {
			putcrlf(conn, "250-ready");
			if (smtputf8 != NULL) {
				putcrlf(conn, "250-8BITMIME");
				putcrlf(conn, "250-SMTPUTF8");
			}
			if (xoauth != NULL) {
				putcrlf(conn, "250-AUTH XOAUTH2");
			}
			putcrlf(conn, "250 I'll buy that for a dollar!");
			continue;
		}
		if (xoauth != NULL) {
			/* XOAUTH2 support enabled; handle AUTH (and EHLO above). */
			if (strncmp(line, "AUTH", 4) == 0) {
				if (strncmp(line, "AUTH XOAUTH2", 12) == 0
				    && strstr(line, xoauth) != NULL) {
					putcrlf(conn, "235 OK come in");
					continue;
				}
				putcrlf(conn, "334 base64-json-err");
				smtp_state = SMTP_XOAUTH_ERR;
				continue;
			}
		}
		putcrlf(conn, "250 I'll buy that for a dollar!");
	}

	if (f)
		fclose(f);

	exit(0);
}

/*
 * Read a line (up to the \r\n)
 */

static ssize_t
getsmtp(int socket, char *data)
{
	ssize_t cc;
	static size_t bytesinbuf = 0;
	static char buffer[LINESIZE * 2];

	for (;;) {
		ssize_t cr_pos = -1;
		ssize_t nl_pos = -1;

		if (bytesinbuf > 0) {
			/*
			 * Find our \r\n
			 */
			for (ssize_t i = 0; i < LINESIZE * 2 && i < cc; ++i) {
				if (buffer[i] == '\r') {
					cr_pos = i;
				} else if (cr_pos == i - 1  &&	buffer[i] == '\n') {
					nl_pos = i;
					break;
				}
			}

			if (cr_pos > -1 && nl_pos > -1) {
				cc = cr_pos;
				buffer[cc] = '\0';
				memcpy(data, buffer, min(cc + 1, LINESIZE));
				data[LINESIZE - 1] = '\0';

				/*
				 * Shuffle leftover bytes back to the beginning
				 */

				bytesinbuf -= cc + 2;	/* Don't forget \r\n */
				if (bytesinbuf > 0) {
					memmove(buffer, buffer + cc + 2, bytesinbuf);
				}
			} else {
				/* No CR LF.  Copy all of the data. */
				memcpy(data, buffer, min(cc, LINESIZE));

				/*
				 * Shuffle leftover bytes back to the beginning
				 */

				bytesinbuf -= cc;
				if (bytesinbuf > 0) {
					memmove(buffer, buffer + cc, bytesinbuf);
				}
			}
			return cc;
		}

		if (bytesinbuf >= sizeof(buffer)) {
			fprintf(stderr, "Buffer overflow in getsmtp()!\n");
			exit(1);
		}

		memset(buffer + bytesinbuf, 0, sizeof(buffer) - bytesinbuf);
		cc = read(socket, buffer + bytesinbuf,
			  sizeof(buffer) - bytesinbuf);

		if (cc < 0) {
			fprintf(stderr, "Read failed: %s\n", strerror(errno));
			exit(1);
		}

		if (cc == 0)
			return -1;

		bytesinbuf += cc;
	}
}
