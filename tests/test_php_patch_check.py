"""The PHP runtime-state check must catch the false-clean case, and must
refuse to claim 'patched' when it cannot see.

Written against the real failure mode: PHP's 2026-10-21 advisory says a running
process keeps vulnerable code in memory after the on-disk package is replaced,
so a version string alone reports 'patched' on an exploitable host.
"""
import unittest

from nkama_fact_benchmark import php_patch_check as ppc


class VersionClassification(unittest.TestCase):
    def test_below_fixed_release_fails(self):
        self.assertEqual(ppc.classify_version((8, 4, 26))["status"], "fail")
        self.assertEqual(ppc.classify_version((8, 3, 35))["status"], "fail")
        self.assertEqual(ppc.classify_version((8, 2, 34))["status"], "fail")
        self.assertEqual(ppc.classify_version((8, 5, 11))["status"], "fail")

    def test_at_or_above_fixed_release_passes(self):
        for version in [(8, 5, 12), (8, 4, 27), (8, 3, 36), (8, 2, 35), (8, 4, 30)]:
            self.assertEqual(
                ppc.classify_version(version)["status"], "pass", msg=str(version)
            )

    def test_branch_without_upstream_fix_blocks_rather_than_cries_wolf(self):
        # 8.1 and older got no upstream release. A distro backport may have
        # patched them, which a version string cannot show. Reporting these as
        # 'vulnerable' would make the tool untrustworthy on Debian/RHEL builds.
        for version in [(8, 1, 30), (8, 0, 30), (7, 4, 33)]:
            verdict = ppc.classify_version(version)
            self.assertEqual(verdict["status"], "blocked", msg=str(version))
            self.assertIn("backport", verdict["reason"])

    def test_unknown_or_unparsable_blocks(self):
        self.assertEqual(ppc.classify_version((8, 6, 0))["status"], "blocked")
        self.assertEqual(ppc.classify_version(None)["status"], "blocked")

    def test_parse_version_reads_real_php_v_output(self):
        real = "PHP 8.4.27 (cli) (built: Oct 21 2026 11:02:03) (NTS)"
        self.assertEqual(ppc.parse_version(real), (8, 4, 27))


class StaleRuntimeDetection(unittest.TestCase):
    # Real-shaped /proc/<pid>/maps lines.
    PATCHED_BUT_NOT_RESTARTED = (
        "7f3c1a000000-7f3c1a400000 r-xp 00000000 fd:01 1310745 "
        "/usr/lib/php/8.4/libphp.so (deleted)\n"
        "7f3c1a400000-7f3c1a401000 rw-p 00000000 00:00 0 \n"
        "55a1b2c00000-55a1b2d00000 r-xp 00000000 fd:01 1310800 /usr/sbin/php-fpm8.4\n"
    )
    PROPERLY_RESTARTED = (
        "7f3c1a000000-7f3c1a400000 r-xp 00000000 fd:01 1310999 "
        "/usr/lib/php/8.4/libphp.so\n"
        "55a1b2c00000-55a1b2d00000 r-xp 00000000 fd:01 1310800 /usr/sbin/php-fpm8.4\n"
    )
    NO_PHP_AT_ALL = (
        "55a1b2c00000-55a1b2d00000 r-xp 00000000 fd:01 99 /usr/sbin/nginx\n"
    )

    def test_detects_replaced_runtime_still_resident(self):
        result = ppc.parse_maps(self.PATCHED_BUT_NOT_RESTARTED)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["php_runtime_resident"])
        self.assertEqual(result["deleted_mappings"], ["/usr/lib/php/8.4/libphp.so"])

    def test_restarted_process_is_clean(self):
        result = ppc.parse_maps(self.PROPERLY_RESTARTED)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["php_runtime_resident"])
        self.assertEqual(result["deleted_mappings"], [])

    def test_non_php_process_is_not_flagged(self):
        result = ppc.parse_maps(self.NO_PHP_AT_ALL)
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["php_runtime_resident"])


class RefusesToOverclaim(unittest.TestCase):
    def test_check_never_reports_patched_without_seeing_processes(self):
        # On a host with no /proc (macOS) or no PHP, the only honest verdicts
        # are 'blocked' or 'vulnerable' — never 'patched'.
        report = ppc.check()
        self.assertIn(
            report["verdict"], {"patched", "stale_runtime", "vulnerable", "blocked"}
        )
        if report["running"]["status"] == "blocked":
            self.assertNotEqual(
                report["verdict"],
                "patched",
                msg="claimed patched while the running-process check was blocked",
            )

    def test_report_states_its_own_limits_and_the_pending_cve(self):
        report = ppc.check()
        joined = " ".join(report["limitations"])
        self.assertIn("Linux-only", joined)
        self.assertIn("CVE-2026-115560", joined)
        self.assertEqual(report["cves"], ["CVE-2026-109618", "CVE-2026-109619"])


if __name__ == "__main__":
    unittest.main()
