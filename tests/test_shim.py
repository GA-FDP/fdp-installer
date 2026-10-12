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


def _home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def test_extra_mounts_ignores_args_inside_cwd(tmp_path):
    home = _home(tmp_path)
    cwd = home / "proj"
    cwd.mkdir()
    (cwd / "s.py").write_text("")
    assert shim.extra_mounts(["run", "python", str(cwd / "s.py")], cwd=str(cwd), home=str(home)) == []


def test_extra_mounts_mounts_parent_of_outside_path_read_only(tmp_path):
    home = _home(tmp_path)
    other = home / "elsewhere"
    other.mkdir()
    script = other / "s.py"
    script.write_text("")
    cwd = home / "proj"
    cwd.mkdir()
    r = os.path.realpath(other)
    assert shim.extra_mounts(["run", "python", str(script)], cwd=str(cwd), home=str(home)) == [f"{r}:{r}:ro"]


def test_extra_mounts_dedupes_and_skips_nonpaths(tmp_path):
    home = _home(tmp_path)
    other = home / "o"
    other.mkdir()
    (other / "a").write_text("")
    (other / "b").write_text("")
    cwd = home / "p"
    cwd.mkdir()
    args = ["run", "python", str(other / "a"), str(other / "b"), "--flag", "not/a/real/path"]
    r = os.path.realpath(other)
    assert shim.extra_mounts(args, cwd=str(cwd), home=str(home)) == [f"{r}:{r}:ro"]


def test_extra_mounts_never_mounts_home_itself(tmp_path):
    home = _home(tmp_path)
    cwd = home / "p"
    cwd.mkdir()
    (home / "top.py").write_text("")
    assert shim.extra_mounts(["run", "python", str(home / "top.py")],
                             cwd=str(cwd), home=str(home)) == []


def test_extra_mounts_ignores_paths_outside_home(tmp_path):
    home = _home(tmp_path)
    cwd = home / "p"
    cwd.mkdir()
    assert shim.extra_mounts(["run", "/usr/bin"], cwd=str(cwd), home=str(home)) == []


def test_extra_mounts_ignores_relative_args(tmp_path, monkeypatch):
    home = _home(tmp_path)
    cwd = home / "p"
    cwd.mkdir()
    other = home / "o"
    other.mkdir()
    (other / "s.py").write_text("")
    monkeypatch.chdir(other)
    assert shim.extra_mounts(["run", "python", "s.py"], cwd=str(cwd), home=str(home)) == []


def test_extra_mounts_symlink_mounts_real_dir_at_written_path(tmp_path):
    t = os.path.realpath(tmp_path)
    home = os.path.join(t, "home")
    os.makedirs(os.path.join(home, "real"))
    os.makedirs(os.path.join(home, "proj"))
    open(os.path.join(home, "real", "s.py"), "w").close()
    os.symlink(os.path.join(home, "real"), os.path.join(home, "link"))
    got = shim.extra_mounts(["run", os.path.join(home, "link", "s.py")],
                            cwd=os.path.join(home, "proj"), home=home)
    assert got == [f"{home}/real:{home}/link:ro"]


HOME = "/Users/alice"
CWD = "/Users/alice/proj"


def _cmd(args, runtime="podman", tty=False, env=None, mounts=(), cwd=CWD):
    return shim.build_command(args, runtime=runtime, cwd=cwd, home=HOME,
                              env=env or {}, tty=tty, image="ghcr.io/ga-fdp/fdp:1.28.0",
                              extra=list(mounts))


def test_build_command_podman_basic():
    cmd = _cmd(["run", "python", "s.py"])
    assert cmd == [
        "podman", "run", "--rm", "-i", "--platform", "linux/amd64",
        "-v", f"{HOME}/.fdp:/home/fdp/.fdp",
        "-v", f"{HOME}/.config/pelican:/home/fdp/.config/pelican",
        "-v", f"{CWD}:{CWD}", "-w", CWD,
        "ghcr.io/ga-fdp/fdp:1.28.0", "run", "python", "s.py",
    ]


def test_build_command_tty_adds_t_only_when_interactive():
    assert "-t" in _cmd(["login"], tty=True)
    assert "-it" not in _cmd(["login"], tty=True)
    assert "-t" not in _cmd(["login"], tty=False)
    assert "-i" in _cmd(["login"], tty=False)
    assert "-i" in _cmd(["login"], tty=True)


def test_build_command_refuses_root_cwd():
    with pytest.raises(shim.ShimError):
        _cmd(["ls", "/"], cwd="/")


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
    assert _cmd(["env"]) is None


def test_build_command_env_guard_sees_through_device_flag():
    assert _cmd(["-D", "cmod", "env"]) is None
    assert _cmd(["--device=cmod", "env"]) is None
    assert _cmd(["run", "env"]) is not None


def test_rosetta_warning_silent_when_podman_reports_true():
    assert shim.rosetta_warning("podman", lambda cmd: "true\n") is None


def test_rosetta_warning_when_podman_reports_false():
    msg = shim.rosetta_warning("podman", lambda cmd: "false\n")
    assert "QEMU" in msg and "rosetta" in msg.lower()


def test_rosetta_warning_silent_for_other_runtimes_and_on_error():
    assert shim.rosetta_warning("docker", lambda cmd: "false") is None
    def boom(cmd):
        raise OSError("no machine")
    assert shim.rosetta_warning("podman", boom) is None


def test_rosetta_marker_present_skips_probe(tmp_path):
    m = tmp_path / "ok"
    m.write_text("")
    calls = []
    def run(cmd):
        calls.append(cmd)
        return "false"
    assert shim.rosetta_warning("podman", run, marker=str(m)) is None
    assert calls == []


def test_rosetta_marker_written_after_true_not_after_false(tmp_path):
    m = tmp_path / "ok"
    assert shim.rosetta_warning("podman", lambda c: "true", marker=str(m)) is None
    assert m.exists()
    m2 = tmp_path / "bad"
    assert shim.rosetta_warning("podman", lambda c: "false", marker=str(m2)) is not None
    assert not m2.exists()


class _Recorder:
    def __init__(self):
        self.argv = None
        self.err = []

    def execvp(self, prog, argv):
        self.argv = argv
        raise SystemExit(0)


def _main(args, tmp_path, env=None, tty=False, which_avail=("podman",), rosetta="true"):
    rec = _Recorder()
    env = {"HOME": str(tmp_path), **(env or {})}
    cwd = tmp_path / "proj"
    cwd.mkdir(exist_ok=True)
    with pytest.raises(SystemExit) as e:
        shim.main(args, env=env, cwd=str(cwd), tty=lambda: tty,
                  which=_which_factory(set(which_avail)), execvp=rec.execvp,
                  run=lambda cmd: rosetta, stderr=rec.err.append)
    return e.value.code, rec


def test_main_execs_the_runtime(tmp_path):
    code, rec = _main(["ls", "/"], tmp_path)
    assert code == 0
    assert rec.argv[0] == "podman" and rec.argv[-2:] == ["ls", "/"]
    cwd = str(tmp_path / "proj")
    assert rec.argv[rec.argv.index("-w") + 1] == cwd
    assert f"{cwd}:{cwd}" in rec.argv


def test_main_rosetta_marker_is_written_under_fdp_dir(tmp_path):
    _main(["ls", "/"], tmp_path)
    assert (tmp_path / ".fdp" / "rosetta-checked").exists()


def test_main_creates_the_two_state_dirs(tmp_path):
    _main(["login"], tmp_path)
    assert (tmp_path / ".fdp").is_dir()
    assert (tmp_path / ".config" / "pelican").is_dir()


def test_main_env_prints_message_and_exits_zero(tmp_path):
    code, rec = _main(["env"], tmp_path)
    assert code == 0
    assert rec.argv is None
    assert any("fdp run" in m for m in rec.err)


def test_main_no_runtime_is_exit_2_with_hint(tmp_path):
    code, rec = _main(["ls", "/"], tmp_path, which_avail=())
    assert code == 2
    assert any("brew install podman" in m for m in rec.err)


def test_main_warns_on_rosetta_off(tmp_path):
    _, rec = _main(["ls", "/"], tmp_path, rosetta="false")
    assert any("QEMU" in m for m in rec.err)


def test_main_uses_baked_image(tmp_path):
    _, rec = _main(["ls", "/"], tmp_path)
    assert shim.IMAGE in rec.argv


def test_main_refuses_root_cwd(tmp_path):
    rec = _Recorder()
    with pytest.raises(SystemExit) as e:
        shim.main(["ls", "/"], env={"HOME": str(tmp_path)}, cwd="/", tty=lambda: False,
                  which=_which_factory({"podman"}), execvp=rec.execvp,
                  run=lambda cmd: "true", stderr=rec.err.append)
    assert e.value.code == 2
    assert rec.argv is None
    assert any("refusing" in m for m in rec.err)


def test_main_tty_adds_t_flag(tmp_path):
    _, rec = _main(["login"], tmp_path, tty=True)
    assert "-t" in rec.argv and "-i" in rec.argv
    _, rec = _main(["login"], tmp_path, tty=False)
    assert "-t" not in rec.argv and "-i" in rec.argv
