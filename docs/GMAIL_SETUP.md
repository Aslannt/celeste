# Gmail setup for Celeste V0.4.1

Celeste uses the official Gmail API and Google's OAuth 2.0 desktop-app flow. It does not ask for or store the Gmail account password.

## 1. Create/choose a Google Cloud project

In Google Cloud Console:

1. Create or select a project dedicated to Celeste.
2. Enable **Gmail API** for that project.
3. Open **Google Auth platform** and configure the consent screen/audience for your account.
4. Create an OAuth client with application type **Desktop app**.
5. Download the client JSON.

Google's Gmail Python quickstart documents this project/API/consent/Desktop-app flow.

## 2. Put the client JSON in Celeste's ignored secrets directory

Create this directory locally if needed:

```text
celeste-core/.secrets/
```

Save the downloaded file as:

```text
celeste-core/.secrets/gmail-credentials.json
```

Both the directory and common Gmail credential/token names are ignored by Git. Never commit either OAuth file, especially because the repository may be publicly visible.

## 3. Enable Gmail in `.env`

Keep the existing private Celeste token and add:

```dotenv
CELESTE_GMAIL_ENABLED=true
```

The defaults are:

```text
celeste-core/.secrets/gmail-credentials.json
celeste-core/.secrets/gmail-token.json
```

You only need `CELESTE_GMAIL_CREDENTIALS_FILE` or `CELESTE_GMAIL_TOKEN_FILE` if you want different local paths.

## 4. Authorize from Windows

From `celeste-core`:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\connect_gmail_windows.ps1
```

Celeste opens Google's OAuth flow in the browser. After you approve it, the refresh/access token is stored locally in:

```text
celeste-core/.secrets/gmail-token.json
```

If the requested OAuth scopes change later, delete the local Gmail token and run the authorization helper again so Google can grant the updated scopes.

## Scopes

V0.4.1 requests only:

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.compose
```

`gmail.readonly` lets Celeste read/search mail. `gmail.compose` lets it manage drafts and send mail. Celeste deliberately does not request the broad `https://mail.google.com/` scope and does not expose permanent deletion.

## Tool permissions

```text
gmail_list_unread          READ
gmail_search               READ
gmail_read_message         READ
gmail_create_draft         SAFE_WRITE
gmail_create_reply_draft   SAFE_WRITE
gmail_send_draft           CONFIRM
```

The important separation is **draft first, send second**. Creating a draft never sends it. Sending an existing draft remains pending until the user explicitly confirms the `gmail_send_draft` action.

## Optional unread monitor and Celeste notices

Automatic inbox monitoring is **off by default**. On-demand Gmail tools continue to work when it is off.

After OAuth has been validated, you can opt in with:

```dotenv
CELESTE_GMAIL_POLL_SECONDS=60
```

A non-zero interval is clamped between 60 and 3600 seconds. The monitor only reads unread-message metadata and creates deduplicated local notices. It does not read full bodies, create drafts, reply, or send anything automatically.

Local notices live in:

```text
CelesteBrain/.celeste/notifications.sqlite3
```

They are operational state, not Brain memories. Android V0.4.1 refreshes the notice feed while the app is active and can show a Gmail notice with **Preguntar** and **Descartar** actions. **Preguntar** only prepares a request for Celeste; it does not automatically send a response.

For a one-off poll without enabling background monitoring:

```text
POST /api/v1/integrations/gmail/poll
```

The notice feed is available at:

```text
GET /api/v1/notifications
```

## Initial validation

After authorization and restarting Core:

1. `GET /api/v1/integrations/gmail/status` should show `enabled: true` and `authorized: true`.
2. With `local_rules`, ask: `Que correos no leidos tengo?`
3. Run one manual `POST /api/v1/integrations/gmail/poll` and verify a local notice appears without sending anything.
4. With the OpenAI provider, test natural requests such as `Resume mis correos no leidos`.
5. Ask Celeste to prepare a reply draft and verify it appears as a draft in Gmail.
6. Verify no mail is delivered before the Android/Core confirmation is accepted.
7. Test Cancel first; then perform one intentional confirmation using a harmless test recipient/message.
8. Only after the above works, optionally enable `CELESTE_GMAIL_POLL_SECONDS=60` and test the notice feed with a new unread email.

## Security notes

Email is untrusted external input. Celeste marks returned Gmail data as untrusted and instructs the AI provider never to execute instructions found inside an email body.

OAuth credentials stay inside Celeste Core. Android receives neither the Google client secret nor the refresh token. Tool audit logs record only capability/risk/outcome metadata and intentionally omit email bodies, recipients, subjects, tool arguments and human-readable confirmation summaries.
