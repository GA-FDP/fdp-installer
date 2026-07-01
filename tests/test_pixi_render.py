import importlib.util
import os

_SPEC = importlib.util.spec_from_file_location(
    "fdp_install",
    os.path.join(os.path.dirname(__file__), "..", "fdp_installer", "bin", "fdp_install.py"),
)
fdp_install = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fdp_install)
render_pixi_toml = fdp_install.render_pixi_toml


def test_default_uses_stable_core():
    text = render_pixi_toml()
    assert 'fdp-core = "*"' in text
    assert "fdp-core-latest" not in text
    assert "[feature.cmf]" not in text


def test_latest_flavor():
    text = render_pixi_toml(latest=True)
    assert 'fdp-core-latest = "*"' in text
    assert 'fdp-core = "*"' not in text


def test_with_cmf_adds_feature_and_pins():
    text = render_pixi_toml(with_cmf=True)
    assert "[feature.cmf]" in text
    assert "protobuf" in text and "<5" in text
    assert 'paramiko = "==3.4.1"' in text
    assert "cmflib" in text  # pypi git dep
    assert 'cmf = ["cmf"]' in text or 'cmf"' in text  # environment wired


def test_with_labeler_adds_package():
    text = render_pixi_toml(with_labeler=True)
    assert "ga-dfl-labeler" in text
