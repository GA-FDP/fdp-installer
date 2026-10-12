import importlib.util
import os
import tomllib

_SPEC = importlib.util.spec_from_file_location(
    "fdp_install",
    os.path.join(os.path.dirname(__file__), "..", "fdp_installer", "bin", "fdp_install.py"),
)
fdp_install = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fdp_install)
render_pixi_toml = fdp_install.render_pixi_toml
write_pixi_toml = fdp_install.write_pixi_toml


def test_default_uses_stable_core():
    text = render_pixi_toml()
    assert 'fdp-core = "*"' in text
    assert "fdp-core-latest" not in text
    assert "[feature.cmf.dependencies]" not in text


def test_latest_flavor():
    text = render_pixi_toml(latest=True)
    assert 'fdp-core-latest = "*"' in text
    assert 'fdp-core = "*"' not in text


def test_no_cmf_feature_and_no_pip_install():
    """CMF arrives via the fdp-core metapackage, not a pixi feature.

    Until 2026-09-02 cmflib had to be a pixi pypi-dependency pointing at a git
    fork, because ml-metadata was pip-only and could not appear in a conda
    metapackage. Both are conda packages on ga-fdp now, so fdp-core carries
    cmflib directly and --with-cmf is gone. Nothing here should reintroduce a
    pip path.
    """
    for kwargs in ({}, {"latest": True}, {"with_labeler": True}):
        text = render_pixi_toml(**kwargs)
        assert "[feature.cmf.dependencies]" not in text, kwargs
        assert "pypi-dependencies" not in text, kwargs
        assert "cmflib" not in text, kwargs
        assert "github.com/sammuli/cmf" not in text, kwargs


def test_with_cmf_argument_is_gone():
    """render_pixi_toml no longer accepts with_cmf."""
    import pytest

    with pytest.raises(TypeError):
        render_pixi_toml(with_cmf=True)


def test_with_labeler_adds_package():
    text = render_pixi_toml(with_labeler=True)
    assert "ga-dfl-labeler" in text
    assert 'ga-dfl-labeler = "==1.0.0"' in text


def test_all_combinations_parse_as_toml():
    import tomllib
    combos = [
        ({}, ["dev"]),
        ({"latest": True}, ["dev"]),
        ({"with_labeler": True}, ["dev"]),
        ({"latest": True, "with_labeler": True}, ["dev"]),
    ]
    for kwargs, expected_default in combos:
        text = render_pixi_toml(**kwargs)
        doc = tomllib.loads(text)  # raises on malformed TOML
        assert doc["environments"]["default"] == expected_default, kwargs


def test_write_pixi_toml_writes_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_pixi_toml()
    assert (tmp_path / "pixi.toml").exists()
    assert 'fdp-core = "*"' in (tmp_path / "pixi.toml").read_text()


def test_write_pixi_toml_skips_when_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pixi.toml").write_text("SENTINEL")
    write_pixi_toml()
    assert (tmp_path / "pixi.toml").read_text() == "SENTINEL"


def test_no_activation_default_device():
    # The installer does not pick a device for the user; fdp-core is
    # multi-device and the fdp CLI requires an explicit choice.
    assert "FDP_DEFAULT_DEVICE" not in render_pixi_toml()


def test_core_version_pins_exactly():
    text = render_pixi_toml(core_version="1.28.0")
    assert 'fdp-core = "==1.28.0"' in text
    assert 'fdp-core = "*"' not in text


def test_core_version_with_latest_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        render_pixi_toml(latest=True, core_version="1.28.0")


def test_core_version_parses_as_toml():
    doc = tomllib.loads(render_pixi_toml(core_version="1.28.0"))
    assert doc["dependencies"]["fdp-core"] == "==1.28.0"


def test_render_subcommand_prints_pinned_toml(capsys):
    fdp_install.main(["render", "--core-version", "1.28.0"])
    out = capsys.readouterr().out
    doc = tomllib.loads(out)
    assert doc["dependencies"]["fdp-core"] == "==1.28.0"
