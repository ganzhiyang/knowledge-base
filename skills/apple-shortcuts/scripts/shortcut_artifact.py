#!/usr/bin/env python3
"""Inspect/compare Shortcut artifacts without running their actions.

Signed AEA inspection uses macOS tools to verify the archive signature against
its embedded certificate's public key. This checks package integrity, NOT
independent certificate-chain trust or runtime behavior on an iPhone.
"""

import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys
import tempfile
from xml.parsers.expat import ExpatError

MAX_BYTES = 64 * 1024 * 1024
METADATA_NORMALIZATIONS = {"WFWorkflowName", "WFWorkflowClientVersion"}
IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,256}\Z")
TRUST_BOUNDARY = (
    "Archive signature verified with embedded certificate public key; "
    "independent certificate-chain trust and device execution NOT verified."
)


class ArtifactError(ValueError):
    pass


def read_bytes(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ArtifactError("Artifact exceeds 64 MiB limit")
    return data


def native_run(args, timeout):
    """Do not echo native output, which may contain user data or local paths."""
    if sys.platform != "darwin":
        raise ArtifactError("Signed AEA inspection/signing requires macOS native tools")
    try:
        result = subprocess.run(args, check=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ArtifactError(f"{Path(args[0]).name} timed out after {timeout}s") from exc
    except subprocess.CalledProcessError as exc:
        raise ArtifactError(f"{Path(args[0]).name} failed (exit {exc.returncode}); no output replaced") from exc
    except OSError as exc:
        raise ArtifactError(f"Cannot start native tool {Path(args[0]).name}") from exc
    return result.stdout


def validate_workflow(workflow):
    if not isinstance(workflow, dict):
        raise ArtifactError("Workflow root must be a dictionary")
    actions = workflow.get("WFWorkflowActions")
    if not isinstance(actions, list):
        raise ArtifactError("Workflow must contain a WFWorkflowActions array")
    for action in actions:
        if not isinstance(action, dict) or not isinstance(action.get("WFWorkflowActionIdentifier"), str):
            raise ArtifactError("Each action must have a string WFWorkflowActionIdentifier")
        if not IDENTIFIER.fullmatch(action["WFWorkflowActionIdentifier"]):
            raise ArtifactError("Invalid action identifier")
        if "WFWorkflowActionParameters" in action and not isinstance(action["WFWorkflowActionParameters"], dict):
            raise ArtifactError("Action parameters must be a dictionary")
    if "WFWorkflowTriggers" in workflow:
        if not isinstance(workflow["WFWorkflowTriggers"], list):
            raise ArtifactError("WFWorkflowTriggers must be an array")
        for trigger in workflow["WFWorkflowTriggers"]:
            if not isinstance(trigger, dict) or not isinstance(trigger.get("WFTriggerIdentifier"), str):
                raise ArtifactError("Each trigger must have a string WFTriggerIdentifier")
            if not IDENTIFIER.fullmatch(trigger["WFTriggerIdentifier"]):
                raise ArtifactError("Invalid trigger identifier")
    for key in ("WFWorkflowInputContentItemClasses", "WFWorkflowOutputContentItemClasses"):
        if key in workflow and (not isinstance(workflow[key], list) or any(
            not isinstance(value, str) or not IDENTIFIER.fullmatch(value) for value in workflow[key]
        )):
            raise ArtifactError(f"{key} must be an array of class identifiers")
    for key in METADATA_NORMALIZATIONS:
        if key in workflow and not isinstance(workflow[key], str):
            raise ArtifactError(f"{key} must be a string when present")
    canonical(workflow)
    return workflow


def parse_plain(data):
    try:
        if data.lstrip().startswith(b"{"):
            workflow = json.loads(data, object_pairs_hook=unique_keys)
            kind = "json"
        else:
            workflow = plistlib.loads(data)
            kind = "plist"
        return validate_workflow(workflow), kind
    except (json.JSONDecodeError, plistlib.InvalidFileException, ExpatError, UnicodeError, OverflowError, TypeError) as exc:
        raise ArtifactError("Malformed JSON/plist workflow") from exc


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactError("Duplicate JSON dictionary key")
        result[key] = value
    return result


def extract_signed(path, package):
    if len(package) < 12:
        raise ArtifactError("Truncated AEA header")
    header_size = struct.unpack("<I", package[8:12])[0]
    if header_size < 1 or header_size > len(package) - 12:
        raise ArtifactError("Invalid AEA header size")
    try:
        header = plistlib.loads(package[12:12 + header_size])
        chain = header["SigningCertificateChain"]
        certificate = chain[0]
        if not isinstance(chain, list) or not isinstance(certificate, bytes) or not certificate:
            raise ValueError("Invalid certificate")
    except (plistlib.InvalidFileException, ExpatError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise ArtifactError("AEA header does not contain an embedded signing certificate") from exc
    with tempfile.TemporaryDirectory(prefix="shortcut-inspect-") as scratch:
        root = Path(scratch)
        # Work from the exact bytes inspected, avoiding changes to the input mid-check.
        archive_input = root / "input.shortcut"
        archive_input.write_bytes(package)
        cert = root / "certificate.der"
        cert.write_bytes(certificate)
        pubkey = root / "public.pem"
        pubkey.write_bytes(native_run([
            "/usr/bin/openssl", "x509", "-inform", "DER", "-in", str(cert), "-pubkey", "-noout"
        ], 10))
        archive = root / "payload.aar"
        native_run(["/usr/bin/aea", "decrypt", "-i", str(archive_input), "-o", str(archive),
                    "-sign-pub", str(pubkey)], 15)
        extracted = root / "extracted"
        extracted.mkdir()
        native_run(["/usr/bin/aa", "extract", "-i", str(archive), "-d", str(extracted),
                    "-include-path", "Shortcut.wflow"], 15)
        workflow_path = extracted / "Shortcut.wflow"
        if workflow_path.is_symlink() or not workflow_path.is_file():
            raise ArtifactError("Signed archive lacks a regular Shortcut.wflow payload")
        workflow, _ = parse_plain(read_bytes(workflow_path))
        return workflow


def load_artifact(path):
    data = read_bytes(path)
    if data.startswith(b"AEA1"):
        workflow = extract_signed(path, data)
        kind = "signed-aea"
    else:
        workflow, kind = parse_plain(data)
    return workflow, kind, hashlib.sha256(data).hexdigest()


def canonical(value):
    """Type-sensitive tree: false differs from 0, and absent differs from null."""
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ArtifactError("Dictionary keys must be strings")
        return ["dict", [[key, canonical(value[key])] for key in sorted(value)]]
    if isinstance(value, list):
        return ["list", [canonical(item) for item in value]]
    if isinstance(value, bytes):
        return ["bytes", base64.b64encode(value).decode("ascii")]
    if isinstance(value, datetime.datetime):
        return ["datetime", value.isoformat()]
    if isinstance(value, plistlib.UID):
        return ["uid", value.data]
    if value is None or type(value) in (str, bool, int, float):
        # Forbid non-finite JSON numerics, which have no useful plist equivalent.
        try:
            json.dumps(value, allow_nan=False)
        except ValueError as exc:
            raise ArtifactError("Non-finite numeric workflow value") from exc
        return [type(value).__name__, value]
    raise ArtifactError("Unsupported workflow value type")


def compare_workflows(expected, actual):
    validate_workflow(expected)
    validate_workflow(actual)
    # Observed Apple signer behavior omits the root name. A changed or newly
    # introduced name is not normalization: it can break name-based handoffs.
    if "WFWorkflowName" in actual and (
        "WFWorkflowName" not in expected or actual["WFWorkflowName"] != expected["WFWorkflowName"]
    ):
        raise ArtifactError("Workflow name changed or was added; reject publication")
    left = {key: value for key, value in expected.items() if key not in METADATA_NORMALIZATIONS}
    right = {key: value for key, value in actual.items() if key not in METADATA_NORMALIZATIONS}
    if canonical(left) != canonical(right):
        # Do not print key names/values from unknown fields: they can contain secrets.
        raise ArtifactError("Workflow differs beyond client-version normalization/root-name omission; reject publication")
    changes = []
    key = "WFWorkflowClientVersion"
    if (key in expected) != (key in actual) or expected.get(key) != actual.get(key):
        changes.append({"field": key, "change": "normalized"})
    if "WFWorkflowName" in expected and "WFWorkflowName" not in actual:
        changes.append({"field": "WFWorkflowName", "change": "omitted"})
    return changes


def summary(workflow, kind, digest):
    canonical_bytes = json.dumps(canonical(workflow), ensure_ascii=False, separators=(",", ":")).encode()
    return {
        "format": kind,
        "artifact_sha256": digest,
        "workflow_tree_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "action_count": len(workflow["WFWorkflowActions"]),
        "action_identifiers": sorted({action["WFWorkflowActionIdentifier"] for action in workflow["WFWorkflowActions"]}),
        "trigger_count": len(workflow.get("WFWorkflowTriggers", [])),
        "trigger_identifiers": sorted({trigger["WFTriggerIdentifier"] for trigger in workflow.get("WFWorkflowTriggers", [])}),
        "input_classes": workflow.get("WFWorkflowInputContentItemClasses", []),
        "output_classes": workflow.get("WFWorkflowOutputContentItemClasses", []),
        "execution_tested": False,
        "signature_check": TRUST_BOUNDARY if kind == "signed-aea" else "Unsigned artifact; no signature checked",
    }


def sign_candidate(source, output, mode):
    """Replace the local output only after verifying the signed candidate."""
    expected, kind, _ = load_artifact(source)
    if kind == "signed-aea":
        raise ArtifactError("Sign expects a reviewed unsigned JSON/plist workflow")
    target = Path(output)
    if target.suffix != ".shortcut":
        raise ArtifactError("Output must use the .shortcut extension")
    if Path(source).resolve() == target.resolve():
        raise ArtifactError("Source and signed output must be separate files")
    # Same parent allows atomic replacement; existing output survives all failures.
    with tempfile.TemporaryDirectory(prefix=".shortcut-sign-", dir=target.parent) as scratch:
        root = Path(scratch)
        unsigned = root / "source.shortcut"
        unsigned.write_bytes(plistlib.dumps(expected, fmt=plistlib.FMT_BINARY, sort_keys=False))
        candidate = root / "candidate.shortcut"
        native_run(["/usr/bin/shortcuts", "sign", "--mode", mode, "--input", str(unsigned),
                    "--output", str(candidate)], 60)
        actual, candidate_kind, digest = load_artifact(candidate)
        if candidate_kind != "signed-aea":
            raise ArtifactError("Signer did not produce a signed AEA archive")
        normalizations = compare_workflows(expected, actual)
        os.replace(candidate, target)
    result = summary(actual, candidate_kind, digest)
    result["permitted_metadata_changes"] = normalizations
    result["output_written"] = True
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Summarize without running actions or dumping parameters")
    inspect.add_argument("artifact", type=Path)
    compare = commands.add_parser("compare", help="Compare full workflow; permit only client-version normalization/root-name omission")
    compare.add_argument("expected", type=Path)
    compare.add_argument("actual", type=Path)
    sign = commands.add_parser("sign", help="Sign with Apple's CLI, verify and atomically replace output")
    sign.add_argument("source", type=Path)
    sign.add_argument("output", type=Path)
    sign.add_argument("--mode", choices=("anyone", "people-who-know-me"), default="anyone")
    args = parser.parse_args(argv)
    try:
        if args.command == "sign":
            result = sign_candidate(args.source, args.output, args.mode)
        elif args.command == "compare":
            expected, _, _ = load_artifact(args.expected)
            actual, kind, digest = load_artifact(args.actual)
            changes = compare_workflows(expected, actual)
            result = summary(actual, kind, digest)
            result.update({"workflow_matches": True, "permitted_metadata_changes": changes})
        else:
            workflow, kind, digest = load_artifact(args.artifact)
            result = summary(workflow, kind, digest)
        print(json.dumps(result, indent=2))
        return 0
    except (ArtifactError, OSError, ValueError, RecursionError) as exc:
        # OSError may include private paths. No native stderr or source contents.
        message = str(exc) if isinstance(exc, ArtifactError) else "Cannot read/write or parse artifact"
        print(f"error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
