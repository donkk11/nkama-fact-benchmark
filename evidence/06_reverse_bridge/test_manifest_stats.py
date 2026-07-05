import json
import os
import tempfile
import unittest

import manifest_stats


def write_manifest(checks, allowed=None):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as fh:
        json.dump({"allowed_command_prefixes": allowed or [], "checks": checks}, fh)
    return path


class ManifestStatsTests(unittest.TestCase):
    def test_counts_by_type(self):
        path = write_manifest([
            {"type": "file_exists"},
            {"type": "file_exists"},
            {"type": "command_exit_zero"},
        ])
        summary = manifest_stats.summarize(path)
        self.assertEqual(summary["checks_total"], 3)
        self.assertEqual(summary["by_type"], {"file_exists": 2, "command_exit_zero": 1})

    def test_command_is_strongest_tier(self):
        path = write_manifest([
            {"type": "file_exists"},
            {"type": "command_exit_zero"},
        ])
        self.assertEqual(manifest_stats.summarize(path)["strongest_tier"], "command")

    def test_presence_only_manifest(self):
        path = write_manifest([{"type": "file_exists"}])
        summary = manifest_stats.summarize(path)
        self.assertEqual(summary["strongest_tier"], "presence")
        self.assertFalse(summary["command_checks_allowed"])

    def test_allowed_commands_flag(self):
        path = write_manifest([{"type": "command_exit_zero"}], allowed=[["node"]])
        self.assertTrue(manifest_stats.summarize(path)["command_checks_allowed"])

    def test_rejects_manifest_without_checks(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump({"nothing": True}, fh)
        with self.assertRaises(ValueError):
            manifest_stats.load_manifest(path)


if __name__ == "__main__":
    unittest.main()
