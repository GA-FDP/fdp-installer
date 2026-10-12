# tests/test_shim.py
import os
import pytest

from fdp_installer import shim


def _which_factory(available):
    return lambda name: f"/usr/local/bin/{name}" if name in available else None


def test_find_runtime_prefers_podman():
    assert shim.find_runtime({}, _which_factory({"podman", "docker", "container"})) == "podman"


def test_find_runtime_falls_back_to_docker_then_container():
    assert shim.find_runtime({}, _which_factory({"docker", "container"})) == "docker"
    assert shim.find_runtime({}, _which_factory({"container"})) == "container"


def test_find_runtime_env_override_wins():
    env = {"FDP_CONTAINER_RUNTIME": "docker"}
    assert shim.find_runtime(env, _which_factory({"podman", "docker"})) == "docker"


def test_find_runtime_none_raises_with_install_hint():
    with pytest.raises(shim.ShimError) as e:
        shim.find_runtime({}, _which_factory(set()))
    assert "brew install podman" in str(e.value)
    assert "colima" in str(e.value)


def test_extra_mounts_ignores_args_inside_cwd(tmp_path):
    (tmp_path / "s.py").write_text("")
    assert shim.extra_mounts(["run", "python", "s.py"], cwd=str(tmp_path)) == []
    assert shim.extra_mounts(["run", "python", str(tmp_path / "s.py")], cwd=str(tmp_path)) == []


def test_extra_mounts_mounts_parent_of_outside_path_read_only(tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    script = other / "s.py"
    script.write_text("")
    cwd = tmp_path / "proj"
    cwd.mkdir()
    mounts = shim.extra_mounts(["run", "python", str(script)], cwd=str(cwd))
    assert mounts == [f"{other}:{other}:ro"]


def test_extra_mounts_dedupes_and_skips_nonpaths(tmp_path):
    other = tmp_path / "o"
    other.mkdir()
    (other / "a").write_text("")
    (other / "b").write_text("")
    cwd = tmp_path / "p"
    cwd.mkdir()
    args = ["run", "python", str(other / "a"), str(other / "b"), "--flag", "not/a/real/path"]
    assert shim.extra_mounts(args, cwd=str(cwd)) == [f"{other}:{other}:ro"]


def test_extra_mounts_never_mounts_home_or_root(tmp_path):
    cwd = tmp_path / "p"
    cwd.mkdir()
    home = str(tmp_path)
    (tmp_path / "top.py").write_text("")
    # A file directly under $HOME would mount all of $HOME; refuse that.
    assert shim.extra_mounts(["run", "python", str(tmp_path / "top.py")],
                             cwd=str(cwd), home=home) == []


HOME = "/Users/alice"
CWD = "/Users/alice/proj"


def _cmd(args, runtime="podman", isatty=False, env=None, mounts=()):
    return shim.build_command(args, runtime=runtime, cwd=CWD, home=HOME,
                              env=env or {}, isatty=isatty, image="ghcr.io/ga-fdp/fdp:1.28.0",
                              extra=list(mounts))


def test_build_command_podman_basic():
    cmd = _cmd(["run", "python", "s.py"])
    assert cmd == [
        "podman", "run", "--rm", "--platform", "linux/amd64",
        "-v", f"{HOME}/.fdp:/home/fdp/.fdp",
        "-v", f"{HOME}/.config/pelican:/home/fdp/.config/pelican",
        "-v", f"{CWD}:/work", "-w", "/work",
        "ghcr.io/ga-fdp/fdp:1.28.0", "run", "python", "s.py",
    ]


def test_build_command_tty_adds_it_only_when_interactive():
    assert "-it" in _cmd(["login"], isatty=True)
    assert "-it" not in _cmd(["login"], isatty=False)


def test_build_command_forwards_bearer_token_when_set():
    cmd = _cmd(["ls", "/"], env={"BEARER_TOKEN": "x"})
    assert "-e" in cmd and "BEARER_TOKEN" in cmd
    assert "BEARER_TOKEN" not in _cmd(["ls", "/"])


def test_build_command_forwards_fdp_default_device():
    cmd = _cmd(["ls", "/"], env={"FDP_DEFAULT_DEVICE": "d3d"})
    assert cmd[cmd.index("-e") + 1] == "FDP_DEFAULT_DEVICE"


def test_build_command_appends_extra_mounts():
    cmd = _cmd(["run", "python", "/x/s.py"], mounts=["/x:/x:ro"])
    i = cmd.index("/x:/x:ro")
    assert cmd[i - 1] == "-v"


def test_build_command_docker_is_same_shape():
    assert _cmd(["ls", "/"], runtime="docker")[0] == "docker"


def test_build_command_apple_container_uses_arch_flag():
    cmd = _cmd(["ls", "/"], runtime="container")
    assert cmd[:2] == ["container", "run"]
    assert "--arch" in cmd and cmd[cmd.index("--arch") + 1] == "amd64"
    assert "--platform" not in cmd


def test_build_command_env_is_a_message_not_a_container():
    assert shim.build_command(["env"], runtime="podman", cwd=CWD, home=HOME,
                              env={}, isatty=True, image="i", extra=[]) is None


def test_rosetta_warning_silent_when_podman_reports_true():
    run = lambda cmd: "true\n"
    assert shim.rosetta_warning("podman", run) is None


def test_rosetta_warning_when_podman_reports_false():
    run = lambda cmd: "false\n"
    msg = shim.rosetta_warning("podman", run)
    assert "QEMU" in msg and "rosetta" in msg.lower()


def test_rosetta_warning_silent_for_other_runtimes_and_on_error():
    assert shim.rosetta_warning("docker", lambda cmd: "false") is None
    def boom(cmd):
        raise OSError("no machine")
    assert shim.rosetta_warning("podman", boom) is None
