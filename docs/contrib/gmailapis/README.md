# <a href="http://nmh.nongnu.org">nmh</a> <a href="https://developers.google.com/gmail/api">Gmail API</a> Integration

## Privacy Policy
The <a href="http://nmh.nongnu.org">nmh</a> project page contains a link to the
<a href="http://nmh.nongnu.org/privacy.html">nmh Privacy Policy</a>.

## Limited Use Requirements
nmh's use and transfer to any other app of information received from Google APIs will adhere to
<a href="https://developers.google.com/terms/api-services-user-data-policy#additional_requirements_for_specific_api_scopes">Google API Services User Data Policy</a>, including the Limited Use requirements.

## nmh Installation
This module integrates support into nmh for a user to send email messages using
their own Gmail account, and support for a user to incorporate email messages
from their own Gmail  account.  To set up:

1. Download and install nmh as usual.  For now, until nmh receives verification
from Google, nmh support for Gmail APIs is on the `gmailapis` `git` branch.
These commands will download, build, test, and install nmh including its support
for Gmail APIs:
>   `wget http://git.savannah.gnu.org/cgit/nmh.git/plain/build_nmh`\
>   `sh build_nmh -div -b gmailapis`

Respond to the `build_nmh` prompts to customize your nmh installation.  The `Install
prefix` setting is most important; the defaults for the remaining settings should
be acceptable.  Finally, add the location of the installed nmh `bin` and
`share/doc/nmh/contrib/gmailapis` directories to your search `PATH`.  The
nmh `INSTALL` and `MACHINES` files provide further information, notably
including prerequisites such as autoconf, automake, make, and a C compiler.

2. Run the following command and follow
its instructions to update your Python version and/or packages as
necessary:
>   docs/contrib/gmailapis/nmh_gmailapi_prereqs.sh

That, and some commands below, assume that `share/doc/nmh/contrib/gmailapis`
was added to your search PATH.

3. Add a postproc to your nmh profile (assumed to be \~/.mh_profile) using
this shell command:
>   echo postproc: \`mhparam docdir\`/contrib/gmailapis/gpost.py >>\~/.mh_profile

That will cause nmh `send` to use your Gmail account to send mail messages.

4. Login to your Gmail account using:
>   glogin.py -user *your-gmail-username*

Read and follow the prompts.  This requires a graphical user interface such as
X11 and a web browser such as `google-chrome`.

You will then be able to send email messages using nmh `send`.  To incorporate
unread email messages from your Gmail inbox, run this command:
>   ginc.py -user *your-gmail-username*

The `-help` switch to each of the `glogin.py`, `ginc.py`, and `gpost.py`
commands documents other switches that can be used to customize program
behavior.
