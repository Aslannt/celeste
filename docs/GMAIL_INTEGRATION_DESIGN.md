# Gmail integration design

Gmail is planned as a stacked V0.4.1 increment after the V0.4 Tool Router foundation.

## Goals

Celeste should be able to:

1. list/search incoming mail;
2. read a message only when needed;
3. summarize mail using the configured AI provider;
4. prepare a draft or reply draft without sending it;
5. send a draft only after an explicit Celeste `CONFIRM` action.

## Permission model

| Capability | Celeste risk |
| --- | --- |
| Search/list unread mail | `READ` |
| Read one message | `READ` |
| Create a draft | `SAFE_WRITE` |
| Create a reply draft | `SAFE_WRITE` |
| Send an existing draft | `CONFIRM` |
| Delete/trash mail | not exposed initially |

The model never receives Google OAuth credentials. Gmail tools execute inside Celeste Core; the provider only sees the tool schema and the minimum tool output required to answer the user.

Email bodies are untrusted external content. The OpenAI provider instruction explicitly says that instructions found inside notes, email or retrieved messages must be treated as data, not as commands.

## OAuth

Use Google's OAuth 2.0 installed/desktop application flow for the owner's account. Credentials and refresh tokens stay in a local ignored directory such as `celeste-core/.secrets/`.

Planned scopes:

- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.compose`

`gmail.compose` is needed for creating and sending drafts. We deliberately avoid the all-powerful `https://mail.google.com/` scope and do not expose permanent deletion.

Changing scopes requires re-authorizing the local token.

## Safe send flow

```text
User asks Celeste to reply
        |
        v
READ original message
        |
        v
SAFE_WRITE create reply draft
        |
        v
Celeste shows recipient/subject + asks permission
        |
        v
CONFIRM gmail_send_draft
        |
        v
Gmail sends only after user confirmation
```

A draft-first approach also leaves a visible artifact in Gmail before anything is sent.

## Notifications

Initial V0.4.1 should prioritize correct OAuth, reading, drafting and confirmed sending. Continuous inbox monitoring and Android notifications are a separate follow-up because Core currently runs on the user's PC rather than a 24/7 server.

When monitoring is added, prefer Gmail history/push mechanisms or a conservative polling interval; do not expose Gmail credentials to Android.
