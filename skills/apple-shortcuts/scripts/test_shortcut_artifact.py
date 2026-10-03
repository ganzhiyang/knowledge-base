#!/usr/bin/env python3
"""Portable helper tests: no native signing, Shortcut installation or execution."""

import contextlib
import copy
import io
import json
from pathlib import Path
import plistlib
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import shortcut_artifact as helper


def fixture():
    return {
        "WFWorkflowName": "Example",
        "WFWorkflowClientVersion": "1234",
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFWalletTransactionContentItem"],
        "WFWorkflowActions": [{
            "WFWorkflowActionIdentifier": "is.workflow.actions.comment",
            "WFWorkflowActionParameters": {"WFCommentActionText": "private-value-not-for-output", "Enabled": False},
        }],
        "WFWorkflowTriggers": [{
            "WFTriggerIdentifier": "WFWalletTransactionTrigger",
            "WFTriggerUUID": "example-trigger-id",
            "WFTriggerSerializedParameters": {},
        }],
    }


class CompareTests(unittest.TestCase):
    def test_roundtrip_json_xml_binary_plist(self):
        expected = fixture()
        for data in (json.dumps(expected).encode(), plistlib.dumps(expected),
                     plistlib.dumps(expected, fmt=plistlib.FMT_BINARY)):
            with self.subTest(header=data[:6]):
                actual, _ = helper.parse_plain(data)
                self.assertEqual(helper.compare_workflows(expected, actual), [])

    def test_only_root_name_omission_and_client_version_can_normalize(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        del actual["WFWorkflowName"]
        actual["WFWorkflowClientVersion"] = "2345"
        self.assertEqual(helper.compare_workflows(expected, actual),
                         [{"field": "WFWorkflowClientVersion", "change": "normalized"},
                          {"field": "WFWorkflowName", "change": "omitted"}])
        actual["WFWorkflowActions"][0]["WFWorkflowActionParameters"]["WFWorkflowName"] = "hidden"
        with self.assertRaises(helper.ArtifactError):
            helper.compare_workflows(expected, actual)

    def test_changed_name_rejected_to_preserve_name_based_handoffs(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        actual["WFWorkflowName"] = "Example 2"
        with self.assertRaisesRegex(helper.ArtifactError, "name changed or was added"):
            helper.compare_workflows(expected, actual)

    def test_added_name_rejected_when_expected_has_no_name(self):
        actual = fixture()
        expected = copy.deepcopy(actual)
        del expected["WFWorkflowName"]
        with self.assertRaisesRegex(helper.ArtifactError, "name changed or was added"):
            helper.compare_workflows(expected, actual)

    def test_name_omission_is_reported_explicitly(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        del actual["WFWorkflowName"]
        self.assertEqual(helper.compare_workflows(expected, actual),
                         [{"field": "WFWorkflowName", "change": "omitted"}])

    def test_all_workflow_drift_rejected(self):
        expected = fixture()
        variants = []
        changed = copy.deepcopy(expected)
        del changed["WFWorkflowTriggers"]
        variants.append(("removed trigger", changed))
        changed = copy.deepcopy(expected)
        changed["WFWorkflowTriggers"][0]["WFTriggerSerializedParameters"] = {"Enabled": False}
        variants.append(("changed trigger", changed))
        changed = copy.deepcopy(expected)
        changed["WFWorkflowActions"].append(copy.deepcopy(changed["WFWorkflowActions"][0]))
        variants.append(("extra action", changed))
        changed = copy.deepcopy(expected)
        changed["WFWorkflowActions"][0]["WFWorkflowActionParameters"]["Enabled"] = 0
        variants.append(("boolean versus integer", changed))
        changed = copy.deepcopy(expected)
        changed["WFWorkflowInputContentItemClasses"] = ["WFStringContentItem"]
        variants.append(("input class", changed))
        changed = copy.deepcopy(expected)
        changed["WFWorkflowMinimumClientVersion"] = 9999
        variants.append(("minimum version", changed))
        changed = copy.deepcopy(expected)
        changed["WFWorkflowActions"][0]["WFWorkflowActionParameters"]["NewValue"] = None
        variants.append(("missing versus null", changed))
        for label, actual in variants:
            with self.subTest(change=label), self.assertRaises(helper.ArtifactError):
                helper.compare_workflows(expected, actual)

    def test_trigger_absence_is_not_normalized_to_empty_array(self):
        expected = fixture()
        del expected["WFWorkflowTriggers"]
        actual = copy.deepcopy(expected)
        actual["WFWorkflowTriggers"] = []
        with self.assertRaises(helper.ArtifactError):
            helper.compare_workflows(expected, actual)

    def test_summary_does_not_dump_parameters_or_workflow_name(self):
        workflow = fixture()
        workflow["WFWorkflowName"] = "private-workflow-name"
        result = helper.summary(workflow, "plist", "examplehash")
        encoded = json.dumps(result)
        self.assertNotIn("private-value-not-for-output", encoded)
        self.assertNotIn("private-workflow-name", encoded)
        self.assertEqual(result["action_count"], 1)
        self.assertEqual(result["trigger_count"], 1)
        self.assertFalse(result["execution_tested"])
        signed = helper.summary(workflow, "signed-aea", "examplehash")
        self.assertIn("independent certificate-chain trust", signed["signature_check"])
        self.assertIn("NOT verified", signed["signature_check"])


class InvalidInputTests(unittest.TestCase):
    def test_malformed_formats_fail_cleanly_without_echoing_contents(self):
        examples = [
            b"private-garbage", b'{"WFWorkflowActions":', b"[]", b"bplist00bad",
            b'{"WFWorkflowActions":[],"WFWorkflowActions":[]}',
            b'{"WFWorkflowActions":[],"WFWorkflowTriggers":{}}',
            b'{"WFWorkflowActions":[],"WFWorkflowName":{}}',
            b'{"WFWorkflowActions":[{}]}',
            b'<?xml version="1.0"?><plist><dict><key>x</key>',
            b'{"WFWorkflowActions":[],"value":NaN}',
            b"AEA1", b"AEA1" + b"\0" * 4 + struct.pack("<I", 10000),
        ]
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "input.shortcut"
            for data in examples:
                with self.subTest(header=data[:24]):
                    path.write_bytes(data)
                    output, errors = io.StringIO(), io.StringIO()
                    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                        self.assertEqual(helper.main(["inspect", str(path)]), 1)
                    self.assertEqual(output.getvalue(), "")
                    self.assertNotIn("private-garbage", errors.getvalue())

    def test_aea_without_certificate_rejected_before_native_commands(self):
        header = plistlib.dumps({"SigningCertificateChain": []})
        package = b"AEA1" + b"\0" * 4 + struct.pack("<I", len(header)) + header
        with patch.object(helper, "native_run") as native:
            with self.assertRaises(helper.ArtifactError):
                helper.extract_signed(Path("unused.shortcut"), package)
            native.assert_not_called()

    def test_signed_inspection_requires_macOS(self):
        with patch.object(helper.sys, "platform", "linux"), patch.object(helper.subprocess, "run") as native:
            with self.assertRaisesRegex(helper.ArtifactError, "requires macOS"):
                helper.native_run(["/usr/bin/aea", "decrypt"], 15)
            native.assert_not_called()

    def test_native_command_timeout_is_bounded_and_output_redacted(self):
        with patch.object(helper.sys, "platform", "darwin"), patch.object(
            helper.subprocess, "run", side_effect=subprocess.TimeoutExpired("secret-command", 5, stderr=b"private")
        ) as run:
            with self.assertRaisesRegex(helper.ArtifactError, "timed out after 5s"):
                helper.native_run(["/usr/bin/aa", "extract"], 5)
            self.assertEqual(run.call_args.kwargs["timeout"], 5)


class PublicationGateTests(unittest.TestCase):
    def test_rejected_signer_preserves_existing_output(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        del actual["WFWorkflowTriggers"]
        with tempfile.TemporaryDirectory() as root:
            source, output = Path(root) / "source.json", Path(root) / "live.shortcut"
            source.write_text(json.dumps(expected))
            output.write_bytes(b"previous-verified-release")
            # Simulates extracted payload only; no native signing or installation.
            def fake_native(args, timeout):
                Path(args[-1]).write_bytes(b"candidate")
                return b""
            with patch.object(helper, "native_run", side_effect=fake_native), patch.object(
                helper, "load_artifact", side_effect=[(expected, "json", "a"), (actual, "signed-aea", "b")]
            ):
                with self.assertRaises(helper.ArtifactError):
                    helper.sign_candidate(source, output, "anyone")
            self.assertEqual(output.read_bytes(), b"previous-verified-release")
            self.assertEqual(sorted(item.name for item in Path(root).iterdir()), ["live.shortcut", "source.json"])

    def test_verified_candidate_replaces_local_output_without_claiming_publication(self):
        expected = fixture()
        actual = copy.deepcopy(expected)
        actual["WFWorkflowClientVersion"] = "2345"
        with tempfile.TemporaryDirectory() as root:
            source, output = Path(root) / "source.json", Path(root) / "live.shortcut"
            source.write_text(json.dumps(expected))
            output.write_bytes(b"old-release")
            def fake_native(args, timeout):
                Path(args[-1]).write_bytes(b"verified-candidate")
                return b""
            with patch.object(helper, "native_run", side_effect=fake_native), patch.object(
                helper, "load_artifact", side_effect=[(expected, "json", "a"), (actual, "signed-aea", "b")]
            ):
                result = helper.sign_candidate(source, output, "anyone")
            self.assertEqual(output.read_bytes(), b"verified-candidate")
            self.assertTrue(result["output_written"])
            self.assertNotIn("published", result)
            self.assertEqual(result["permitted_metadata_changes"],
                             [{"field": "WFWorkflowClientVersion", "change": "normalized"}])


if __name__ == "__main__":
    unittest.main()
