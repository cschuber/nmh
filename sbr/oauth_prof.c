/* oauth_prof.c -- OAuth 2.0 implementation for XOAUTH2 in SMTP and POP3.
 *
 * This code is Copyright (c) 2014, by the authors of nmh.  See the
 * COPYRIGHT file in the root directory of the nmh distribution for
 * complete copyright information.
 */

#include "h/mh.h"
#include "concat.h"
#include "getcpy.h"
#include "context_find.h"

#ifdef OAUTH_SUPPORT

#include <sys/stat.h>

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>

#include "oauth.h"
#include "oauth_prof.h"
#include "utils.h"
#include "m_maildir.h"

static char client_id[] =
    "\xcd\xce\xc7\xcb\xc7\xca\xcd\xc6\xcb\xcb\xcb\xcd\xd2\xc9\xc9\x9d\xc8\x8c"
    "\xcd\x9a\x95\x89\xca\xc9\x95\x95\xca\xcb\x8b\x8d\xc8\x8b\x92\x9a\x9b\x97"
    "\xcd\x9d\x97\xc9\x8f\x90\x9a\x97\x89\xd1\x9e\x8f\x8f\x8c\xd1\x98\x90\x90"
    "\x98\x93\x9a\x8a\x8c\x9a\x8d\x9c\x90\x91\x8b\x9a\x91\x8b\xd1\x9c\x90\x92";

static char client_secret[] =
    "\xc7\xad\x8c\xcb\xcc\xa6\xbe\xa8\x92\x99\xcd\xce\x8e\xc8\xb9\xb7\xb7\x8e"
    "\x9e\x98\xbc\x94\xbc\x9c";

static const char *scopes[] = {
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    NULL /* must be NULL terminated */
};

static const struct mh_oauth_service_info SERVICES[] = {
    /* https://developers.google.com/accounts/docs/OAuth2InstalledApp */
    {
        /* name */ "gmail",
        /* display_name */ "Gmail",
        /* client_id */ client_id,
        /* client_secret */ client_secret,
        /* auth_endpoint */ "https://accounts.google.com/o/oauth2/auth",
        /* redirect_uri */ "urn:ietf:wg:oauth:2.0:oob",
        /* token_endpoint */ "https://oauth2.googleapis.com/token",
        /* scopes */ scopes,
        /* send_scope_index */ 0,
    }
};

/* Decode a string that was obfuscated by XOR's with 0xff.  Caller
   must free the result. */
static char *
decode(const char *in) {
    char *out = strdup(in);
    for (char *cp = out; *cp; ++cp) {
        *cp ^= 0xff;
    }

    return out;
}

/* Copy service info so we don't have to free it only sometimes. */
static void
copy_svc(mh_oauth_service_info *to, const mh_oauth_service_info *from)
{
    size_t num_scopes = 1; /* account for the final NULL here */
    const char **tp, **fp;

#define copy(_field_) to->_field_ = getcpy(from->_field_)
    copy(name);
    to->display_name = from->display_name;
    copy(auth_endpoint);
    copy(redirect_uri);
    copy(token_endpoint);
#undef copy
    to->client_id = decode(from->client_id);
    to->client_secret = decode(from->client_secret);

    for (fp = from->scopes; *fp; ++fp, ++num_scopes) {}
    to->scopes = mh_xcalloc(num_scopes, sizeof from->scopes[0]);
    for (tp = to->scopes, fp = from->scopes; *fp; ++tp, ++fp) {
        *tp = getcpy(*fp);
    }
    *tp = NULL;
    to->send_scope_index = from->send_scope_index;
}

/* Return profile component node name for a service parameter. */
static char *
mh_oauth_node_name_for_svc(const char *base_name, const char *svc)
{
    /* TODO: s/_/-/g ? */
    return concat("oauth-", svc, "-", base_name, NULL);
}

/* Update one service_info field if overridden in profile. */
static void
update_svc_field(char **field, const char *base_name, const char *svc)
{
    char *name = mh_oauth_node_name_for_svc(base_name, svc);
    const char *value = context_find(name);
    if (value != NULL) {
        free(*field);
        *field = mh_xstrdup(value);
    }
    free(name);
}

/* Update scopes if overridden in profile. */
static bool
update_scopes(const char ***scopes, const char *svc, char *errbuf, size_t errbuflen)
{
    char *name = mh_oauth_node_name_for_svc("scope", svc);
    char *value = context_find(name);
    if (value != NULL) {
        size_t num_scopes = 1; /* account for the final NULL here */
        const char **tp;
        char *new_scopes, *fp;

        /* free the old scopes */
        for (const char **sp = *scopes; sp && *sp; ++sp) {
            free((char *) *sp);
        }
        free(*scopes);

        /* The scopes must be space separated in profile.  This will break if
           a scope contains a space, but that shouldn't happen. */
        /* count the number of scopes */
        new_scopes = mh_xstrdup(value);
        if (strtok(new_scopes, " ")) { ++num_scopes; }
        while (strtok(NULL, " ")) { ++num_scopes; }
        free(new_scopes);

        /* Allocate space for the new scopes and copy them. */
        tp = *scopes = mh_xcalloc(num_scopes, sizeof **scopes);
        if ((fp = strtok(value, " "))) {
            *tp++ = getcpy(fp);
        }
        while ((fp = strtok(NULL, " "))) {
            *tp++ = getcpy(fp);
        }
        *tp = NULL;
        free(value);
    }
    free(name);

    if (*scopes == NULL) {
	trunccpy(errbuf, "scope is missing", errbuflen);
        return false;
    }
    return true;
}

/* Update all service_info fields that are overridden in profile. */
static bool
update_svc(mh_oauth_service_info *svc, const char *svc_name, char *errbuf,
	   size_t errbuflen)
{
    if (! update_scopes(&svc->scopes, svc_name, errbuf, errbuflen)) {
        return false;
    }

#define update(name)                                                    \
    update_svc_field(&svc->name, #name, svc_name);                       \
    if (svc->name == NULL) {                                             \
	trunccpy(errbuf, #name " is missing", errbuflen);		 \
        return false;                                                    \
    }
    update(client_id);
    update(client_secret);
    update(auth_endpoint);
    update(redirect_uri);
    update(token_endpoint);
#undef update

    if (svc->name == NULL) {
        svc->name = getcpy(svc_name);
    }

    if (svc->display_name == NULL) {
        svc->display_name = svc->name;
    }

    return true;
}

bool
mh_oauth_get_service_info(const char *svc_name, mh_oauth_service_info *svcinfo,
			  char *errbuf, size_t errbuflen)
{
    int i;

    svcinfo->name = svcinfo->display_name = svcinfo->client_id = NULL;
    svcinfo->client_secret = svcinfo->auth_endpoint = NULL;
    svcinfo->redirect_uri = svcinfo->token_endpoint = NULL;
    svcinfo->scopes = NULL;
    svcinfo->send_scope_index = 0;

    for (i = 0; i < (int)DIM(SERVICES); i++) {
        if (strcmp(SERVICES[i].name, svc_name) == 0) {
            copy_svc(svcinfo, &SERVICES[i]);
            break;
        }
    }

    return update_svc(svcinfo, svc_name, errbuf, errbuflen);
}

/* Return value must be free(3)'d. */
char *
mh_oauth_cred_fn(const char *svc)
{
    char *key = mh_oauth_node_name_for_svc("credential-file", svc);
    char *value = context_find(key);
    free(key);

    bool found = value;
    if (found) {
        if (*value == '/')
            return mh_xstrdup(value);
    } else
        value = concat("oauth-", svc, NULL);

    const char *md = m_maildir(value);
    if (!found)
        free(value);

    return mh_xstrdup(md);
}
#endif
