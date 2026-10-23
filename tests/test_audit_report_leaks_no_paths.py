"""Guard: the audit report itself must not leak the auditor's local paths.

A security-audit report is meant to be published as evidence. If it echoes the
resolved artifact path, it exposes the auditor's username and directory layout
— the same class of thing the report's own no_internal_paths finding rejects
inside the artifact.
"""
import json, pathlib, re, tempfile, unittest, zipfile

from nkama_fact_benchmark.security import audit_artifacts

BAD = re.compile(r"/Users/|/home/[a-z]|[A-Z]:\\\\Users")


class AuditReportLeaksNoPaths(unittest.TestCase):
    def test_report_carries_filename_not_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = pathlib.Path(tmp) / "deeply" / "nested" / "dir"
            nested.mkdir(parents=True)
            wheel = nested / "demo_pkg-0.0.1-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as zf:
                zf.writestr("demo_pkg/__init__.py", "__version__ = '0.0.1'\n")
                zf.writestr("demo_pkg-0.0.1.dist-info/METADATA", "Name: demo-pkg\n")
                zf.writestr("demo_pkg-0.0.1.dist-info/WHEEL", "Wheel-Version: 1.0\n")
                zf.writestr("demo_pkg-0.0.1.dist-info/entry_points.txt", "")

            report = audit_artifacts([str(wheel)])

            self.assertEqual(report["artifacts"][0]["artifact"], wheel.name)
            serialized = json.dumps(report)
            self.assertNotIn(str(nested), serialized)
            self.assertIsNone(
                BAD.search(serialized),
                f"audit report leaked a local path: {serialized[:400]}",
            )


if __name__ == "__main__":
    unittest.main()
