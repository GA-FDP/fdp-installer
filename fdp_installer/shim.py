#!/usr/bin/env python3
"""fdp shim for macOS: run every `fdp` command inside the FDP container image.

Standard library only. fdp-install copies this file to <dir>/bin/fdp with
__FDP_IMAGE__ replaced by the image for the installed bless.
"""

import os
import shutil
import subprocess
import sys

IMAGE = os.environ.get("FDP_IMAGE", "__FDP_IMAGE__")
RUNTIMES = ("podman", "docker", "container")
CONTAINER_HOME = "/home/fdp"

INSTALL_HINT = """no container runtime found on PATH.

Install one of the open runtimes and try again:

  brew install podman && podman machine init && podman machine start
  brew install colima docker && colima start --vm-type=vz --vz-rosetta

Set FDP_CONTAINER_RUNTIME=podman|docker|container to choose explicitly."""


class ShimError(Exception):
    pass


def find_runtime(env, which=shutil.which) -> str:
    forced = env.get("FDP_CONTAINER_RUNTIME")
    if forced:
        if forced not in RUNTIMES:
            raise ShimError(f"FDP_CONTAINER_RUNTIME={forced!r}; expected one of {RUNTIMES}")
        if not which(forced):
            raise ShimError(f"FDP_CONTAINER_RUNTIME={forced} but {forced} is not on PATH")
        return forced
    for name in RUNTIMES:
        if which(name):
            return name
    raise ShimError(INSTALL_HINT)


def extra_mounts(args, cwd, home=None):
    """Read-only mounts so absolute paths named on the command line resolve
    inside the container.

    Only absolute arguments that exist on disk and live under $HOME (not $HOME
    itself) or /Volumes qualify. The current directory is already mounted, and
    anything else (/tmp, /usr, /opt) would shadow the container's own
    filesystem, so it passes through untouched. The parent directory is
    mounted at the path as written, from its resolved location, so the
    argument text stays valid inside the container even through a symlink.
    """
    home = os.path.realpath(home or os.path.expanduser("~"))
    cwd = os.path.realpath(cwd)
    mounts = []
    for arg in args:
        if not os.path.isabs(arg) or not os.path.exists(arg):
            continue
        real = os.path.realpath(arg)
        if real == cwd or real.startswith(cwd + os.sep):
            continue
        written = os.path.normpath(arg)
        if os.path.isdir(real):
            source, target = real, written
        else:
            source, target = os.path.dirname(real), os.path.dirname(written)
        if not (source.startswith(home + os.sep) or source.startswith("/Volumes/")):
            continue
        spec = f"{source}:{target}:ro"
        if spec not in mounts:
            mounts.append(spec)
    return mounts


FORWARDED_ENV = ("BEARER_TOKEN", "FDP_DEFAULT_DEVICE", "FDP_STORE_CATALOG",
                 "FDP_SQL_SNAPSHOT_D3DRDB")

ENV_MESSAGE = """fdp env has no meaning on this host: the FDP environment lives inside a
container, and nothing outside it can import toksearch. Run commands with

  fdp run <command ...>

and they execute inside the environment with your current directory mounted."""


def _subcommand(args):
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-D", "--device"):
            i += 2
            continue
        if a.startswith("--device="):
            i += 1
            continue
        return a
    return None


def build_command(args, *, runtime, cwd, home, env, tty, image, extra):
    """The runtime argv for `fdp <args>`, or None when no container should run.

    tty is True only when the caller has checked both stdin and stdout are TTYs.
    """
    if _subcommand(args) == "env":
        return None
    if cwd == "/":
        raise ShimError("refusing to run from /: cd into a project directory first")
    cmd = [runtime, "run", "--rm", "-i"]
    if runtime == "container":
        cmd += ["--arch", "amd64"]
    else:
        cmd += ["--platform", "linux/amd64"]
    if tty:
        cmd.append("-t")
    cmd += ["-v", f"{home}/.fdp:{CONTAINER_HOME}/.fdp",
            "-v", f"{home}/.config/pelican:{CONTAINER_HOME}/.config/pelican",
            "-v", f"{cwd}:{cwd}", "-w", cwd]
    for spec in extra:
        cmd += ["-v", spec]
    for name in FORWARDED_ENV:
        if env.get(name):
            cmd += ["-e", name]
    cmd.append(image)
    cmd += list(args)
    return cmd


ROSETTA_MESSAGE = """warning: the podman machine has Rosetta disabled, so this x86-64 image
runs under QEMU and will be many times slower than it should be. Recreate
the machine with Rosetta on:

  podman machine stop && podman machine rm
  podman machine init --rosetta=true && podman machine start"""


def _run_capture(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=True).stdout


def rosetta_warning(runtime, run=_run_capture, marker=None):
    """A warning string when a podman machine will emulate rather than translate.

    A marker file records a good verdict so the probe runs once, not per command.
    """
    if runtime != "podman":
        return None
    if marker and os.path.exists(marker):
        return None
    try:
        out = run(["podman", "machine", "inspect", "--format", "{{.Rosetta}}"])
    except Exception:
        return None
    if out.strip().lower() == "false":
        return ROSETTA_MESSAGE
    if marker:
        try:
            open(marker, "w").close()
        except OSError:
            pass
    return None
