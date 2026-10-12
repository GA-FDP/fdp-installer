import importlib.util
import os
import stat

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "fdp_install",
    os.path.join(os.path.dirname(__file__), "..", "fdp_installer", "bin", "fdp_install.py"),
)
fdp_install = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fdp_install)


def test_install_container_mode_writes_shim_with_image_baked(tmp_path):
    calls = []
    fdp_install.install_container_mode(
        tmp_path, core_version="1.28.0", runtime="podman",
        run=lambda cmd: calls.append(cmd))
    shim = tmp_path / "bin" / "fdp"
    text = shim.read_text()
    assert '"ghcr.io/ga-fdp/fdp:1.28.0"' in text
    assert "__FDP_IMAGE__" not in text
    assert text.startswith("#!/usr/bin/env python3")
    assert shim.stat().st_mode & stat.S_IXUSR
    assert calls == [["podman", "pull", "--platform", "linux/amd64", "ghcr.io/ga-fdp/fdp:1.28.0"]]


def test_install_container_mode_resolves_version_from_channel(tmp_path):
    fdp_install.install_container_mode(
        tmp_path, core_version=None, runtime="docker",
        run=lambda cmd: None, latest=lambda: "1.30.0")
    assert "fdp:1.30.0" in (tmp_path / "bin" / "fdp").read_text()


def test_install_container_mode_refuses_latest_flag(tmp_path):
    with pytest.raises(SystemExit):
        fdp_install.main(["--container", "--latest", "-d", str(tmp_path)])


def test_main_container_flag_skips_pixi(tmp_path, monkeypatch):
    monkeypatch.setattr(fdp_install, "check_pixi_installed",
                        lambda: (_ for _ in ()).throw(AssertionError("pixi must not be checked")))
    monkeypatch.setattr(fdp_install, "install_container_mode",
                        lambda d, **kw: (tmp_path / "called").write_text(str(kw)))
    fdp_install.main(["--container", "-d", str(tmp_path), "--core-version", "1.28.0"])
    assert "1.28.0" in (tmp_path / "called").read_text()


def test_main_defaults_to_container_on_darwin(tmp_path, monkeypatch):
    monkeypatch.setattr(fdp_install.sys, "platform", "darwin")
    monkeypatch.setattr(fdp_install, "install_container_mode",
                        lambda d, **kw: (tmp_path / "called").write_text("yes"))
    fdp_install.main(["-d", str(tmp_path), "--core-version", "1.28.0"])
    assert (tmp_path / "called").exists()


def test_render_latest_with_core_version_is_a_clean_error(capsys):
    with pytest.raises(SystemExit) as e:
        fdp_install.main(["render", "--latest", "--core-version", "1.0.0"])
    assert e.value.code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_top_level_help_mentions_render(capsys):
    with pytest.raises(SystemExit):
        fdp_install.main(["--help"])
    assert "render" in capsys.readouterr().out
