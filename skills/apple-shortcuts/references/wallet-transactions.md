# Wallet Transaction input: a worked reference

These observations came from an OS 27 integration in September–October 2026.
Confirm the target OS and issuer behavior before reuse. This is not a bank
history, settlement feed or generic notification parser.

## Trigger and input

For card-tap capture, inspect the native **Transaction / When a card is tapped**
trigger. A Wallet notification trigger supplies a different type and requires a
different extraction contract. See Apple's
[Transaction trigger guide](https://support.apple.com/en-mide/guide/shortcuts/apd65c67538a/ios).

Observed serialization uses `WFWalletTransactionTrigger` and
`WFWalletTransactionContentItem`. A reviewed OS 27 Any Card export used an empty
`WFTriggerSerializedParameters` dictionary; do not generalize this to other triggers.

On the inspected native runtime, `Type: TriggerOutput` resolved to the **same
workflow input** as `Type: ExtensionInput`. Connect URL Text appeared in both.
Modeling independent input streams made the previous tests miss a Text-to-Transaction
failure. The working flow classified shared input first: Text entered setup/check
validation; a non-text native item entered guarded Transaction extraction.
Run Shortcut forwarding must preserve the original Transaction, not just Merchant.

## Extract properties individually

| Property path | Observed content |
| --- | --- |
| Transaction → Card or Pass | Payment-method object; project its display name |
| Transaction → Merchant | Merchant string |
| Transaction → Amount | Currency-amount object |
| Amount → Currency Amount | Decimal number |
| Amount → Currency Code | Currency code string |

Native coercion before Transaction properties used
`WFCoercionVariableAggrandizement` with
`CoercionItemClass: WFWalletTransactionContentItem`, followed by a
`WFPropertyVariableAggrandizement`. Obtain the current export's full shape;
these labels are not nested JSON keys.

Whole-Transaction → Text failed on the user's phone. Whole Amount → Text loses
the clean numeric/currency distinction. Do not infer missing currency from the
app's base currency. The configured matching card name can differ from the bank
title in a Wallet notification. Keep nickname separate from native matching value;
normalize deliberately and validate again server-side.

Generated event IDs and capture timestamps are application fields, not Apple's
transaction ID or settlement time. The inspected properties did not expose a
reliable settlement status. Do not represent a tap as confirmed settlement;
hold any explicit failure/uncertain status for review if the input provides one.

## Device checks and missed events

Inspect the original item with the native Content Graph action before coercion.
A diagnostic can show Get Type, open the graph for the original item, then stop.
Show Result is not interchangeable: its text conversion can repeat the failure.
A caller continues after Run Shortcut returns; a diagnostic-only caller also
needs to stop if further actions must not run.

Use the next ordinary event or an authorized safe fixture, not an unnecessary
purchase. Synthetic objects establish schema behavior but cannot prove issuer
values, locked execution or device permissions. An inspection that stops capture
can miss the payment; explain that consequence. Do not inspect private Wallet
databases or retrieve bank credentials.

If no saved connection matches, report the observed name and whether the event
was saved. A later manual run cannot reconstruct an event that was never queued.
Use one capture automation per intended source to avoid duplicate captures.

The original user eventually reported successful logging. This supports their
specific setup, not every forwarding, lock-state, issuer or currency path.
