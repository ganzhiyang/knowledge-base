---
name: apple-shortcuts
description: Build, debug, sign and distribute installable Apple Shortcuts for iPhone, iPad and Mac, including typed automation input and secure app/API connections. Use for .shortcut workflows and Shortcuts integration, not keyboard shortcuts.
---

# Apple Shortcuts

Create a maintainable workflow and a reviewable installable artifact. Preserve the
requested trigger and behavior through signing; distinguish verified file
structure from actual device execution.

## Choose the relevant path

- **Create or change a workflow:** read [authoring.md](references/authoring.md) for
  source generation, native schemas, typed variables and trigger preservation.
- **Connect to an app or API:** read [app-integration.md](references/app-integration.md)
  for setup handoffs, scoped credentials, offline queues and truthful status.
- **Fix a device error or publish:** read
  [validation-and-release.md](references/validation-and-release.md) for inspection,
  signing, installation, tests and diagnosis.
- **Apple Pay/Wallet specifically:** also read
  [wallet-transactions.md](references/wallet-transactions.md). Do not apply its
  Transaction schema to unrelated automations or notification text.

## Working method

1. Infer input, output, trigger, app endpoint and minimum OS from the project and
   request. Check the target device and build host separately. Ask only for missing
   facts that materially change implementation.
2. Inspect an existing workflow before changing it. For unfamiliar actions or
   triggers, obtain a small native export from the relevant OS, or inspect
   installed action metadata. Record provenance and version. Display labels,
   JSON-looking text and guesses are not action schemas.
3. Keep one maintained source: native export or deterministic generator, according
   to project needs. Generate review JSON/plist from it. Use a minimal native
   prototype for uncertain behavior before building a large workflow around it.
4. Classify external input before coercion. Preserve native objects for property
   access. Keep setup, manual runs and automatic capture as explicit paths; an
   empty run must not manufacture an event.
5. Build the install/connect/test journey alongside the artifact. Separate a
   successful server ping from an event actually being captured and saved.
6. Validate the generated graph, then the **extracted signed graph**. Check native
   runtime assumptions with a minimal isolated probe; an interpreter cannot
   establish Apple's variable/type behavior merely by modeling it.
7. Publish within the authorized scope and report the artifact, version, remaining
   device actions and tests actually completed. A repository push, website release,
   installed Shortcut and iCloud share are separate states.

## Non-obvious constraints

- Signing may normalize or remove fields. Reject action, input-type, import-question
  or trigger drift; never silently remove a requested automation to make signing pass.
- Embedding an automation does not prove its switch is enabled on fresh import,
  permission is granted or locked execution works. Recheck current OS behavior.
- A native Transaction, Notification, File or Rich Text item is not a dictionary
  just because a later action sends JSON. Inspect its type and project properties.
- Do not ship permanent credentials, personal file bookmarks, device identifiers
  or copied third-party actions in a public template. Use synthetic test data.
- Signing sends the workflow to Apple for validation. Inspect/redact the candidate
  first. Keep signing, installation, execution and public sharing within the actual
  request's authorization; invoking this skill alone grants none of them.
- Inspect unknown exports as data; do not execute them to discover their behavior.
  Bound native probes and stop on a timeout or unexpected side effect rather than
  repeatedly invoking the real automation.

## Included tools

`scripts/shortcut_artifact.py` offers `inspect`, `compare` and explicit `sign`
commands. Run `--help` before use. It never installs or executes the workflow.
Python JSON/plist handling is portable; AEA inspection uses macOS `aea`, `aa` and
`openssl`. Its integrity check uses the embedded certificate's public key and is
**not** independent trust-chain validation.

Adapt the workflow to the new project; do not copy the budget app's URLs, accounts,
token formats, currency, storage folders or minimum OS without a reason.
