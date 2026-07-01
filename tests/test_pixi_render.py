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


def test_with_cmf_adds_feature_and_pins():
    text = render_pixi_toml(with_cmf=True)
    assert "[feature.cmf.dependencies]" in text
    assert "[feature.cmf.pypi-dependencies]" in text
    assert "protobuf" in text and "<5" in text
    assert 'paramiko = "==3.4.1"' in text
    assert "cmflib" in text  # pypi git dep
    # cmf feature activated in the default env (installer runs plain `pixi install`)
    assert "cmf" in text.split("[environments]")[1]


def test_with_labeler_adds_package():
    text = render_pixi_toml(with_labeler=True)
    assert "ga-dfl-labeler" in text
    assert 'ga-dfl-labeler = "==1.0.0"' in text


def test_all_combinations_parse_as_toml():
    import tomllib
    combos = [
        ({}, ["dev"]),
        ({"latest": True}, ["dev"]),
        ({"with_cmf": True}, ["dev", "cmf"]),
        ({"with_labeler": True}, ["dev"]),
        ({"latest": True, "with_cmf": True}, ["dev", "cmf"]),
        ({"with_cmf": True, "with_labeler": True}, ["dev", "cmf"]),
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


def test_default_device_is_d3d_in_all_combos():
    import tomllib
    for kwargs in [{}, {"latest": True}, {"with_cmf": True}, {"with_labeler": True}]:
        text = render_pixi_toml(**kwargs)
        doc = tomllib.loads(text)
        assert doc["activation"]["env"]["FDP_DEFAULT_DEVICE"] == "d3d", kwargs
