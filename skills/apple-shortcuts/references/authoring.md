# Authoring workflows from evidence

## Source and schema

Use a native export for a small UI-authored workflow; a deterministic Python
builder is useful when generation, branching or repeatable releases justify it.
Generated JSON is a review representation, not a second source to hand-edit.

Observed plist fields include `WFWorkflowActions`, `WFWorkflowActionIdentifier`,
`WFWorkflowActionParameters`, `WFWorkflowInputContentItemClasses`,
`WFWorkflowImportQuestions`, and, on supporting OS versions, `WFWorkflowTriggers`.
These are serialization observations, not a guaranteed stable public authoring
API. Inspect current exports before adding unfamiliar fields or enum values.

For each unfamiliar action, establish identifier, parameter keys, allowed values,
input/output type and variable reference shape. Inspect supplied exports read-only;
retain provenance and omit their credentials, personal selectors and unrelated logic.

For generated graphs, stable UUIDv5 values namespaced to the new project make
diffs reproducible. Use matching grouping IDs for If/Otherwise/End If and Repeat
blocks. Verify nested repeat variables resolve to the intended level: `Repeat Item`
and `Repeat Item 2` may refer to different loops.

## Text tokens and native types

Observed token strings use `WFTextTokenString`, U+FFFC placeholders and
`attachmentsByRange`. Offsets are **UTF-16 code units**, not Python character
counts. An emoji before a variable exposes incorrect offsets.

```python
def text_token(*parts):
    value, references = "", {}
    for part in parts:
        if isinstance(part, dict):
            offset = len(value.encode("utf-16-le")) // 2
            references[f"{{{offset}, 1}}"] = part
            value += "\ufffc"
        else:
            value += str(part)
    content = {"string": value}
    if references:
        content["attachmentsByRange"] = references
    return {"Value": content, "WFSerializationType": "WFTextTokenString"}
```

Treat variable **carrier**, declared **content type** and extracted **property**
separately. Keep original input until its type is established, then apply a known
coercion and property projection. A convenience Text action can reject native input.

Dynamic Dictionary Value operands can make the native editor select a different
comparison schema. In the observed text-comparison export, both operands declare
`WFCoercionVariableAggrandizement` with `CoercionItemClass: WFStringContentItem`.
A serialized right-hand value alone did not prevent an iPhone "choose a value for
each parameter" failure. Establish the complete shape for the comparison type
from a native export.

When branching on Get Type, compare with the type of a literal/sample content item
where feasible; avoid assuming English type names on every locale. Guard missing
input before coercion. The Wallet reference explains the observed alias between
`TriggerOutput` and `ExtensionInput` that broke setup/capture branching.

## Triggers and compatibility

Record target OS, authoring/export version and signing-host version separately.
Check [Apple's current release notes](https://support.apple.com/en-us/149045).
OS 27 introduced shareable automations inside Shortcuts; older importers/signers
may not preserve them. Embedding and activation are separate verification steps.

Compare the signed trigger array in full, including selectors and parameters.
An older host in the source project silently removed a newer trigger while still
producing a signed file. Use a compatible signer/export; do not relax expectations.

Use a generic selector only when a current native export demonstrates its shape.
Do not guess that an empty dictionary means "Any" for every trigger. A manual-trigger
alternative is a separate product choice with different setup instructions.

See [provenance](validation-and-release.md#provenance) for the original builder,
native schema investigation and regression tests.
