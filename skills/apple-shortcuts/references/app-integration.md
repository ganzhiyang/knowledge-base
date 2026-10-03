# Connecting a Shortcut to an application

Use these patterns for backend integrations. A local utility that needs no
account or network should remain simpler.

## Install, connect and test

Offer a direct versioned installer and a separate Connect action. Prefer a public,
credential-free template without import questions when the app can supply setup.
Avoid requiring users to copy long JSON blobs.

Apple's [run-shortcut URL scheme](https://support.apple.com/en-au/guide/shortcuts/apd624386f42/ios)
passes text to an **already installed** Shortcut. Encode values with URL APIs.
It neither installs the workflow nor proves it finished. Use Run Shortcut when
calling from another Shortcut.

```javascript
const handoff = new URL('shortcuts://run-shortcut');
handoff.searchParams.set('name', shortcutName);
handoff.searchParams.set('input', 'text');
handoff.searchParams.set('text', JSON.stringify({
  version: 1, action: 'connect', server: location.origin, ticket: oneTimeTicket
}));
```

This is an example protocol, not a prescribed schema. Both sides must agree on
version and actions. Exchange a short-lived, single-use pairing ticket at the
app's backend for a narrow integration credential. Never put owner/admin tokens
or persistent keys in the URL. Keep private runtime configuration separate from
the public template. A consumed ticket whose response was lost needs a new ticket.

Validate expected HTTPS origin, schema and connection identity before saving.
HTTPS syntax alone is not authorization to send secrets anywhere. Bind pairing
to the initiating app origin. Use portable app-scoped storage references, not an
author's private file-provider bookmark.

| Input | Expected behavior |
| --- | --- |
| Valid setup text | Exchange/store configuration; no event capture |
| Scoped test text | Check selected connection; no credential rotation or fake event |
| Native capture item | Extract, validate, queue and deliver |
| No input | Useful instructions or retry queued items, depending on product |
| Unknown input | Explain mismatch before writes or network actions |

## Responses and retries

Get Contents of URL can return Rich Text from an HTML error page despite requesting
JSON. Classify the returned item before Dictionary access or conversion. A correct
server content type helps but does not replace type/field validation.

For valuable events, persist a queue item **before** networking. Generate event ID
and capture time once; retry the same serialized item. Make ingestion idempotent.
Delete only the exact queued file after verified acknowledgment of durable receipt;
an HTTP response or ping alone is insufficient.

Use stable connection identity (such as origin plus connection ID) for storage,
independent of rotating credentials. Scope selected-connection tests before parsing
unrelated configurations so obsolete/corrupt files do not block them. Preserve
unacknowledged items on network, parsing or auth failure. Do not claim an unmatched
event was queued unless the write occurred.

## Feedback and native limits

Distinguish installed, connected, server reached, event received, saved and needing
review. A manual Play cannot reconstruct an earlier native event. Identify the one
check that resolves remaining uncertainty without an unnecessary purchase.

A Shortcut notification and a Home Screen web-app notification are different
channels; use the user's chosen channel. Web Push needs its own opt-in and tests.
Verify the actual server runtime: in the source project, Cloudflare rejected
`redirect: 'error'` before a request left the server. `manual` plus non-2xx handling
preserved the no-redirect policy. This does not make Web Push a requirement for
ordinary Shortcut integrations.
