import importlib.util
import os

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "fdp_install",
    os.path.join(os.path.dirname(__file__), "..", "fdp_installer", "bin", "fdp_install.py"),
)
fdp_install = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fdp_install)


def _host(monkeypatch, tmp_path, sys_platform, machine):
    monkeypatch.setattr(fdp_install.sys, "platform", sys_platform)
    monkeypatch.setattr(fdp_install._platform, "machine", lambda: machine)
    monkeypatch.setattr(fdp_install, "check_pixi_installed", lambda: True)
    monkeypatch.setattr(fdp_install, "install_fdp",
                        lambda d, **kw: (tmp_path / "native").write_text(repr(kw)))


def _apple_silicon(monkeypatch, tmp_path):
    _host(monkeypatch, tmp_path, "darwin", "arm64")


@pytest.mark.parametrize("sys_platform,machine", [
    ("darwin", "x86_64"),
    ("linux", "aarch64"),
])
def test_unsupported_hosts_are_refused(tmp_path, monkeypatch, capsys,
                                       sys_platform, machine):
    _host(monkeypatch, tmp_path, sys_platform, machine)
    with pytest.raises(SystemExit) as e:
        fdp_install.main(["-d", str(tmp_path)])
    assert e.value.code == 2
    err = capsys.readouterr().err
    assert "Linux x86-64" in err and "Apple Silicon" in err
    assert not (tmp_path / "native").exists()


def test_main_is_native_on_linux(tmp_path, monkeypatch):
    _host(monkeypatch, tmp_path, "linux", "x86_64")
    fdp_install.main(["-d", str(tmp_path)])
    assert "'platform': 'linux-64'" in (tmp_path / "native").read_text()


def test_main_is_native_on_apple_silicon(tmp_path, monkeypatch):
    _apple_silicon(monkeypatch, tmp_path)
    fdp_install.main(["-d", str(tmp_path)])
    assert "'platform': 'osx-arm64'" in (tmp_path / "native").read_text()


def test_apple_silicon_refuses_a_core_older_than_its_first(tmp_path, monkeypatch, capsys):
    _apple_silicon(monkeypatch, tmp_path)
    with pytest.raises(SystemExit) as e:
        fdp_install.main(["-d", str(tmp_path), "--core-version", "1.34.0"])
    assert e.value.code == 2
    assert "1.35.0" in capsys.readouterr().err
    assert not (tmp_path / "native").exists()


def test_apple_silicon_accepts_the_first_core_that_installs(tmp_path, monkeypatch):
    _apple_silicon(monkeypatch, tmp_path)
    fdp_install.main(["-d", str(tmp_path), "--core-version", "1.35.0"])
    assert "'core_version': '1.35.0'" in (tmp_path / "native").read_text()


def test_apple_silicon_refuses_the_labeler(tmp_path, monkeypatch, capsys):
    _apple_silicon(monkeypatch, tmp_path)
    with pytest.raises(SystemExit):
        fdp_install.main(["-d", str(tmp_path), "--with-labeler"])
    assert "Linux-only" in capsys.readouterr().err


@pytest.mark.parametrize("sys_platform,machine,expected", [
    ("linux", "x86_64", "linux-64"),
    ("darwin", "arm64", "osx-arm64"),
    ("darwin", "x86_64", None),
    ("linux", "aarch64", None),
])
def test_host_platform(sys_platform, machine, expected):
    assert fdp_install.host_platform(sys_platform, machine) == expected


def test_render_latest_with_core_version_is_a_clean_error(capsys):
    with pytest.raises(SystemExit) as e:
        fdp_install.main(["render", "--latest", "--core-version", "1.0.0"])
    assert e.value.code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_top_level_help_mentions_render(capsys):
    with pytest.raises(SystemExit):
        fdp_install.main(["--help"])
    assert "render" in capsys.readouterr().out
