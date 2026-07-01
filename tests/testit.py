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
        # Run fdp-install once here so all tests have a fully-configured
        # environment regardless of the order in which they execute.
        cls.install_result = subprocess.run(
            ["fdp-install", "-d", str(cls.install_dir)],
            capture_output=True,
            text=True,
        )

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
        """Run a command via pixi in the deployed environment.

        fdp-core is multi-device (d3d + mast) and the fdp CLI requires an
        explicit device choice, so select DIII-D via FDP_DEFAULT_DEVICE for
        these tests (harmless for non-device commands like imports/skills).
        """
        env = {**os.environ, "FDP_DEFAULT_DEVICE": "d3d", **kwargs.pop("env", {})}
        return self._run(
            ["pixi", "run", *args],
            cwd=str(self.install_dir),
            env=env,
            **kwargs,
        )

    def _assert_ok(self, result, msg="Command failed"):
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr)
        self.assertEqual(result.returncode, 0, msg)

    # ── Installation tests ──────────────────────────────────────────

    def test_1_install(self):
        """Verify fdp-install completed successfully."""
        self._assert_ok(self.install_result, "fdp-install failed")

    def test_2_pixi_toml_deployed(self):
        """Verify pixi.toml was written to the target directory."""
        pixi_toml = self.install_dir / "pixi.toml"
        self.assertTrue(pixi_toml.exists(), "pixi.toml not found in install dir")

    def test_3_pixi_env_created(self):
        """Verify pixi created its environment directory."""
        pixi_dir = self.install_dir / ".pixi"
        self.assertTrue(pixi_dir.is_dir(), ".pixi/ directory not created")

    def test_4_imports(self):
        """Verify the fdp-core packages are importable in the deployed env.

        The default install is the slim fdp-core set (no CMF — that is opt-in
        via `fdp-install --with-cmf`), so this imports the core data-access
        stack rather than cmflib.
        """
        result = self._pixi_run(
            "python", "-c",
            "import toksearch, toksearch_d3d, toksearch_mast, fdp, imas_composer; print('OK')",
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
        # First, dump diagnostics for debugging CI failures
        diag_script = textwrap.dedent("""\
            import os, pathlib
            prefix = os.environ.get("CONDA_PREFIX", "NOT SET")
            print(f"CONDA_PREFIX={prefix}")
            print(f"BEARER_TOKEN={'set' if os.environ.get('BEARER_TOKEN') else 'NOT SET'}")
            print(f"XRD_PLUGINCONFDIR={os.environ.get('XRD_PLUGINCONFDIR', 'NOT SET')}")
            print(f"PTDATA_JSON_INDEX_DIR={os.environ.get('PTDATA_JSON_INDEX_DIR', 'NOT SET')}")
            print(f"PTDATA_PLUGIN_LIB={os.environ.get('PTDATA_PLUGIN_LIB', 'NOT SET')}")
            plugdir = os.environ.get("XRD_PLUGINCONFDIR", "")
            if plugdir and pathlib.Path(plugdir).is_dir():
                for f in sorted(pathlib.Path(plugdir).iterdir()):
                    print(f"  plugin conf: {f.name}")
                    print(f"    {f.read_text().strip()}")
            else:
                print(f"  Plugin dir missing or not set")
            libdir = pathlib.Path(prefix) / "lib" if prefix != "NOT SET" else None
            if libdir:
                pelican_libs = sorted(libdir.glob("libXrdClPelican*"))
                print(f"  Pelican libs: {[p.name for p in pelican_libs]}")
        """)
        diag = self._pixi_run("fdp", "run", "python", "-c", diag_script)
        print(diag.stdout)

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


    # ── Skills tests ────────────────────────────────────────────────

    def test_10_skills_install(self):
        """Verify fdp skills install creates skill dirs in ~/.claude/skills/."""
        result = self._pixi_run("fdp", "skills", "install")
        self._assert_ok(result, "fdp skills install failed")

        skills_dir = Path.home() / ".claude" / "skills"
        self.assertTrue(skills_dir.is_dir(), "~/.claude/skills/ was not created")

        installed = [d.name for d in skills_dir.iterdir() if d.is_dir()]
        for skill in ["toksearch-pipeline", "toksearch-d3d-ptdata"]:
            self.assertIn(skill, installed, f"Skill {skill!r} not found in {skills_dir}")

    def test_11_skills_list(self):
        """Verify fdp skills list shows installed skills."""
        result = self._pixi_run("fdp", "skills", "list")
        self._assert_ok(result, "fdp skills list failed")
        for skill in ["toksearch-pipeline", "toksearch-d3d-ptdata"]:
            self.assertIn(skill, result.stdout, f"{skill!r} missing from fdp skills list output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
