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
WORKDIR = "/work"

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
    """Read-only mounts for paths named on the command line outside cwd.

    Only arguments that exist on disk count as paths. The parent directory
    of each is mounted at its own absolute path so the argument text is valid
    inside the container unchanged. $HOME itself and / are never mounted.
    """
    home = os.path.realpath(home or os.path.expanduser("~"))
    cwd = os.path.realpath(cwd)
    mounts = []
    for arg in args:
        if not os.path.exists(arg):
            continue
        real = os.path.realpath(arg)
        if real == cwd or real.startswith(cwd + os.sep):
            continue
        parent = real if os.path.isdir(real) else os.path.dirname(real)
        if parent in ("/", home):
            continue
        spec = f"{parent}:{parent}:ro"
        if spec not in mounts:
            mounts.append(spec)
    return mounts


FORWARDED_ENV = ("BEARER_TOKEN", "FDP_DEFAULT_DEVICE", "FDP_STORE_CATALOG",
                 "FDP_SQL_SNAPSHOT_D3DRDB")

ENV_MESSAGE = """fdp env has no meaning on this host: the FDP environment lives inside a
container, and nothing outside it can import toksearch. Run commands with

  fdp run <command ...>

and they execute inside the environment with your current directory mounted."""


def build_command(args, *, runtime, cwd, home, env, isatty, image, extra):
    """The runtime argv for `fdp <args>`, or None when no container should run."""
    if args[:1] == ["env"]:
        return None
    cmd = [runtime, "run", "--rm"]
    if runtime == "container":
        cmd += ["--arch", "amd64"]
    else:
        cmd += ["--platform", "linux/amd64"]
    if isatty:
        cmd.append("-it")
    cmd += ["-v", f"{home}/.fdp:{CONTAINER_HOME}/.fdp",
            "-v", f"{home}/.config/pelican:{CONTAINER_HOME}/.config/pelican",
            "-v", f"{cwd}:{WORKDIR}", "-w", WORKDIR]
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
    return subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=True).stdout


def rosetta_warning(runtime, run=_run_capture):
    """A warning string when a podman machine will emulate rather than translate."""
    if runtime != "podman":
        return None
    try:
        out = run(["podman", "machine", "inspect", "--format", "{{.Rosetta}}"])
    except Exception:
        return None
    if out.strip().lower() == "false":
        return ROSETTA_MESSAGE
    return None
