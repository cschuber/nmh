# [nmh](http://nmh.nongnu.org) [Gmail API](https://developers.google.com/gmail/api) Integration

## Privacy Policy
The [nmh](http://nmh.nongnu.org) project page contains a link to the
[nmh Privacy Policy](http://nmh.nongnu.org/privacy.html).

## Limited Use Requirements
nmh's use and transfer to any other app of information received from Google APIs will adhere to
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy#additional_requirements_for_specific_api_scopes), including the Limited Use requirements.

## nmh Integration
This module integrates support into nmh for a user to send email messages using
their own Gmail account, and support for a user to incorporate email messages
from their own Gmail  account.  To set up:

1. Install nmh as usual.

2. The commands below assume that \`mhparam docdir\`/contrib/gmailapis was added to your search PATH.

3. The following command checks your Python version and packages.  It
will provide instructions to update them as necessary:<br>
>   nmh_gmailapi_prereqs\.sh

4. To configure nmh `send` to use your Gmail account to send mail messages, add
a postproc to your nmh profile (assumed to be \~/.mh_profile) using this shell
command:<br>
>   echo postproc: \`mhparam docdir\`/contrib/gmailapis/gpost.py >> \~/.mh_profile

5. To log in to your Gmail account:<br>
>   glogin\.py -user *your-gmail-username*

It will prompt to login as necessary.  This requires a graphical user interface
such as X11 and a web browser such as `google-chrome`.

6. To incorporate unread email messages from your Gmail inbox, use the
`ginc.py` command:<br>
>   ginc\.py -user *your-gmail-username*

The `-help` switch to each of the `glogin.py`, `ginc.py`, and `gpost.py`
commands documents other switches that can be used to customize program
behavior.
