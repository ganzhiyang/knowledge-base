# Validation, signing and distribution

## Inspect without executing

From the skill folder:

```sh
python3 scripts/shortcut_artifact.py inspect workflow.shortcut
python3 scripts/shortcut_artifact.py compare expected.plist exported.shortcut
python3 -m unittest discover -s scripts -p 'test_*.py' -v
```

The helper accepts JSON and XML/binary plist. For signed files it uses macOS tools
to extract `Shortcut.wflow` from the observed `AEA1` archive format without running
the workflow. Other formats require appropriate tooling, not guessed parsing.

It verifies archive integrity using the embedded certificate's public key. This
does not establish a trusted Apple certificate chain, benign behavior or native
runtime correctness. Summaries omit parameter values; review any full exported
graph for secrets/personal data before sharing.

## Sign and compare

Apple's [command-line guide](https://support.apple.com/guide/shortcuts-mac/run-shortcuts-from-the-command-line-apd455c82f02/mac)
documents signing, which sends a copy to Apple for validation. For a reviewed,
public credential-free artifact use `--mode anyone`. `people-who-know-me` embeds
contact information and is a different distribution choice.

```sh
python3 scripts/shortcut_artifact.py sign reviewed.json release.shortcut
```

The helper writes a temporary binary plist with a `.shortcut` extension, invokes
the official signer with a timeout, extracts and compares the candidate, and
only then replaces the designated output. It does not install or run the file.
The underlying native command is:

```sh
/usr/bin/shortcuts sign --mode anyone --input candidate.shortcut --output signed.shortcut
```

Actions/parameters, input types, import questions, triggers/selectors and behavioral
root fields must match. The helper allows client-version normalization and the
observed omission of the root name; it rejects a changed or newly introduced name.
A run-shortcut URL calls the installed name, so verify that name and its callers
even when the signer omits name metadata. Do not ignore unknown differences.
Older signers can remove newer fields. Preserve a
compatible signed native export rather than re-sign it on an incompatible host.
Never edit signed bytes; obtain a newly signed artifact after source changes.

Keep failed candidates separate from released sources. Record hashes of source,
extracted payload and signed bytes, artifact version, host/export OS and actual
verification results. A signing or publication failure must not replace a good release.

## Test the right boundaries

| Layer | Useful evidence | Does not prove |
| --- | --- | --- |
| Source/graph | References, UTF-16 tokens, branches, intended trigger | Native parameter validity |
| Signed payload | Actions/trigger retained, archive integrity | Installation, certificate-chain trust |
| Interpreter + API | Setup/capture/retry separation, idempotency, retained queue | Apple's coercion or variable aliasing |
| Isolated native probe | Runtime assumption with synthetic values | Issuer data, iPhone background execution |
| Target-device import | Trigger retained, activation/permissions visible | Successful captured event |
| Authorized real event | Saved fields, acknowledgment, feedback | Reliability across all devices/issuers |

For API integration, cover setup text, empty input, typed capture, unsupported
input, missing fields, locale-sensitive values, HTML/Rich Text replies, auth
failure, offline retry, duplicate submission and key rotation. Run graph tests
against the **extracted signed graph**, and validate modeled behavior natively.

Diagnostic native copies should replace network actions with controlled responses
and use separate storage. Never replace the user's working logger with a diagnostic.
A timed-out run or one stalled at Files permission is partial evidence, not success.

## Deliver a usable installer

Serve signed bytes with a `.shortcut` filename, appropriate binary MIME type and
attachment disposition. Inspect the real CDN/worker route: static hosting can
bypass headers in application code. Match downloaded bytes to the release hash.

Test the installer on the target device/browser. In-app previews may show raw
binary or fail to hand off to Shortcuts. A direct link reduces steps only if the
actual importer works; document a Safari/Files fallback when needed. Do not invent
iCloud URLs. Obtain a native share link, inspect its download and compare the
graph before making it primary. Treat shares as snapshots, not moving release URLs.

Make the version visible, explain Replace for upgrades, and preserve runtime
configuration. Report separately: source pushed, artifact published, installer
verified, device behavior verified. Automation activation and permissions may
remain; promise zero configuration only after a fresh target-device install proves it.

## Diagnose the observed failure

| Symptom | First check |
| --- | --- |
| Browser displays AEA/binary text | Download headers, filename, CDN route, opening app |
| Choose a value for each parameter | Action schema and declared operand types |
| Transaction → Text | Premature whole-item conversion; typed property extraction |
| Text → Transaction during Connect | Shared input classification before property access |
| Rich Text → Dictionary after HTTP | Actual response type, origin, upstream error page |
| Missing installed trigger | Source vs signed graph vs importing OS |
| Ping succeeds, no saved event | Trigger, native matching value, queue write, durable receipt |
| Local tests pass, production fails | Real server runtime and transport response |

Use the highlighted action plus sanitized type/shape evidence. A screenshot does
not expose all runtime fields, a past event or a response body. Keep credentials
out of screenshots, logs and public exports.

## Provenance

Generalized from budget-tracker through commit
`e91f3a429a1a3690cc9b0a5ed4c4fcb2a11d84f8` (2026-10-03):

- [Builder and signing](https://github.com/ganzhiyang/budget-tracker/blob/e91f3a429a1a3690cc9b0a5ed4c4fcb2a11d84f8/tools/build-apple-pay-shortcut.py)
- [Signed-graph tests](https://github.com/ganzhiyang/budget-tracker/blob/e91f3a429a1a3690cc9b0a5ed4c4fcb2a11d84f8/test/shortcut.test.js)
- [Native input-alias probe](https://github.com/ganzhiyang/budget-tracker/blob/e91f3a429a1a3690cc9b0a5ed4c4fcb2a11d84f8/tools/check-shortcut-input-alias.m)
- [Schema/export provenance](https://github.com/ganzhiyang/budget-tracker/blob/e91f3a429a1a3690cc9b0a5ed4c4fcb2a11d84f8/tools/shortcuts/README.md)

Third-party exports informed schema inspection; their workflows are not bundled
or required. Original manifests conservatively mark physical verification false.
A later user report confirmed their logger worked; that does not prove every path.
