# LinkedIn integration assessment

Status: research/design only. No browser scraping or unofficial inbox automation has been added to Celeste.

## What the official platform currently exposes

LinkedIn documents a **Communication APIs** area with Invitation and Messages APIs, but the documentation page itself requires authorization. LinkedIn's Invitations API explicitly says usage is restricted to approved partners. LinkedIn's general API-access documentation also says most permissions and partner programs require explicit approval.

The self-service/open consumer permissions documented by LinkedIn are much narrower:

- OpenID Connect `profile`;
- OpenID Connect `email`;
- `w_member_social` through Share on LinkedIn.

Those open permissions do not provide a normal personal LinkedIn inbox/messages permission.

Official references checked on 2026-08-18:

- https://learn.microsoft.com/en-us/linkedin/shared/integrations/communications/overview
- https://learn.microsoft.com/en-us/linkedin/shared/integrations/communications/invitations
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access
- https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin

## Decision for Celeste

Do not build the personal-message feature around DOM scraping, saved LinkedIn passwords, browser-cookie extraction, or automation that pretends to be an official messaging API.

That would create a fragile and high-risk dependency for a personal assistant that may eventually run unattended.

Instead:

1. keep `linkedin_*` tools out of the Tool Router until the account/app has an official API product that supports the required inbox/message use case;
2. if official access becomes available, keep OAuth tokens inside Celeste Core, never inside the LLM or Android client;
3. model message reads as `READ`, draft/preparation as `SAFE_WRITE`, and external message delivery as `CONFIRM`;
4. treat LinkedIn message content as untrusted external data just like email;
5. keep the connector interface provider-neutral so another supported communication source can be added without changing the assistant architecture.

## Useful LinkedIn capability available sooner

If desired, a later increment can use LinkedIn's self-service **Share on LinkedIn** capability (`w_member_social`) for explicit user-requested posts. Posting would still be a `CONFIRM` action in Celeste.

This is intentionally separate from personal inbox/message access.

## Re-evaluation trigger

Re-check the official LinkedIn Developer Portal and Microsoft Learn documentation before implementing V0.4.2. LinkedIn API products and access rules change over time, so this assessment should not be treated as a permanent platform limitation.
