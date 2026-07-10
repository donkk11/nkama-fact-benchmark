"""Guard: portable examples and re-verify docs must not hardcode local paths.

The evidence/ appendix is historical maintainer-hosted data and is exempt.
"""
import pathlib, re, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAD = re.compile(r"/Users/|/home/[a-z]")
TARGETS = ["examples", "README.md", "RECOMMENDED_RUN.md", "README_PYPI.md"]

class NoAbsolutePaths(unittest.TestCase):
    def test_portable_surface_has_no_local_paths(self):
        offenders = []
        for t in TARGETS:
            p = ROOT / t
            files = p.rglob("*") if p.is_dir() else [p]
            for f in files:
                if f.is_file() and f.suffix in {".json", ".md", ".py", ".txt"}:
                    if BAD.search(f.read_text(encoding="utf-8", errors="ignore")):
                        offenders.append(str(f.relative_to(ROOT)))
        self.assertEqual(offenders, [], f"absolute local paths found: {offenders}")

if __name__ == "__main__":
    unittest.main()
