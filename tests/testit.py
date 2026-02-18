"""End-to-end tests for fdp-install."""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestFdpInstaller(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp(prefix="fdp_test_")
        cls.install_dir = Path(cls.tmpdir) / "fdp_env"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmpdir, ignore_errors=True)

    def _run(self, cmd, **kwargs):
        """Run a command and return the CompletedProcess."""
        print(f"  Running: {' '.join(str(c) for c in cmd)}")
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            **kwargs,
        )

    def _pixi_run(self, *args, **kwargs):
        """Run a command via pixi in the deployed environment."""
        return self._run(
            ["pixi", "run", *args],
            cwd=str(self.install_dir),
            **kwargs,
        )

    def _assert_ok(self, result, msg="Command failed"):
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
        self.assertEqual(result.returncode, 0, msg)

    # ── Installation tests ──────────────────────────────────────────

    def test_1_install(self):
        """Run fdp-install into a fresh temp directory."""
        result = self._run(["fdp-install", "-d", str(self.install_dir)])
        self._assert_ok(result, "fdp-install failed")

    def test_2_pixi_toml_deployed(self):
        """Verify pixi.toml was copied to the target directory."""
        pixi_toml = self.install_dir / "pixi.toml"
        self.assertTrue(pixi_toml.exists(), "pixi.toml not found in install dir")

    def test_3_pixi_env_created(self):
        """Verify pixi created its environment directory."""
        pixi_dir = self.install_dir / ".pixi"
        self.assertTrue(pixi_dir.is_dir(), ".pixi/ directory not created")

    def test_4_imports(self):
        """Verify key packages are importable in the deployed environment."""
        result = self._pixi_run(
            "python", "-c",
            "import toksearch_d3d; import cmflib; print('OK')",
        )
        self._assert_ok(result, "Package imports failed")
        self.assertIn("OK", result.stdout)

    def test_5_idempotent(self):
        """Running the installer again on the same directory should succeed."""
        mtime_before = (self.install_dir / "pixi.toml").stat().st_mtime
        result = self._run(["fdp-install", "-d", str(self.install_dir)])
        self._assert_ok(result, "Second fdp-install run failed")
        mtime_after = (self.install_dir / "pixi.toml").stat().st_mtime
        self.assertEqual(mtime_before, mtime_after,
                         "pixi.toml was overwritten on second run")

    # ── fdp CLI tests ───────────────────────────────────────────────

    def test_6_fdp_env(self):
        """Verify fdp env outputs expected environment variables."""
        result = self._pixi_run("fdp", "env")
        self._assert_ok(result, "fdp env failed")
        for var in ["PTDATA_LOC", "PTDATA_LIBRARY", "XRD_PLUGINCONFDIR",
                     "default_tree_path", "MDS_PATH", "D3DATA"]:
            self.assertIn(var, result.stdout, f"{var} missing from fdp env output")

    def test_7_fdp_run_imports(self):
        """Verify toksearch_d3d imports under fdp run."""
        result = self._pixi_run(
            "fdp", "run", "python", "-c",
            "from toksearch_d3d import PtDataSignal; print('OK')",
        )
        self._assert_ok(result, "fdp run import failed")
        self.assertIn("OK", result.stdout)

    def test_8_fdp_run_ptdata_fetch(self):
        """Fetch real DIII-D data via PtDataSignal under fdp run."""
        script = textwrap.dedent("""\
            from toksearch_d3d import PtDataSignal
            result = PtDataSignal("ip", fetch_times=True, fetch_units=True).fetch(165920)
            assert len(result["data"]) > 0, "No data returned"
            assert len(result["times"]) > 0, "No times returned"
            print(f"Fetched {len(result['data'])} data points")
        """)
        result = self._pixi_run("fdp", "run", "python", "-c", script)
        self._assert_ok(result, "PtDataSignal fetch failed")
        self.assertIn("Fetched", result.stdout)

    def test_9_fdp_ls(self):
        """Verify fdp ls can list the FDP root directory."""
        result = self._pixi_run("fdp", "ls", "/fdp-d3d")
        self._assert_ok(result, "fdp ls failed")
        self.assertTrue(len(result.stdout.strip()) > 0, "fdp ls returned no output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
