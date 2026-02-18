"""End-to-end tests for fdp-install."""

import os
import shutil
import subprocess
import sys
import tempfile
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

    def test_1_install(self):
        """Run fdp-install into a fresh temp directory."""
        result = self._run(["fdp-install", "-d", str(self.install_dir)])
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
        self.assertEqual(result.returncode, 0, "fdp-install failed")

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
        result = self._run(
            ["pixi", "run", "python", "-c",
             "import toksearch_d3d; import cmflib; print('OK')"],
            cwd=str(self.install_dir),
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
        self.assertEqual(result.returncode, 0, "Package imports failed")
        self.assertIn("OK", result.stdout)

    def test_5_idempotent(self):
        """Running the installer again on the same directory should succeed."""
        mtime_before = (self.install_dir / "pixi.toml").stat().st_mtime
        result = self._run(["fdp-install", "-d", str(self.install_dir)])
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
        self.assertEqual(result.returncode, 0, "Second fdp-install run failed")
        mtime_after = (self.install_dir / "pixi.toml").stat().st_mtime
        self.assertEqual(mtime_before, mtime_after,
                         "pixi.toml was overwritten on second run")


if __name__ == "__main__":
    unittest.main(verbosity=2)
