#!/usr/bin/env python3
"""
FDP Installer - Bootstrap script for Fusion Data Platform installation
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
import stat

from fdp_installer import channel, shim as _shim_module

IMAGE_REPO = "ghcr.io/ga-fdp/fdp"


_LABELER_DEP = 'ga-dfl-labeler = "==1.0.0"  # carries a glibc <2.35 constraint'


def render_pixi_toml(latest: bool = False, with_labeler: bool = False,
                     core_version: "str | None" = None) -> str:
    if latest and core_version:
        raise ValueError("--latest and --core-version are mutually exclusive")
    core = "fdp-core-latest" if latest else "fdp-core"
    spec = f"=={core_version}" if core_version else "*"
    deps = [f'{core} = "{spec}"']
    if with_labeler:
        deps.append(_LABELER_DEP)
    envs = ["dev"]
    text = f'''[workspace]
name = "fdp_dev"
description = "Fusion Data Platform environment (slim core via fdp-core metapackage)"
channels = ["conda-forge", "ga-fdp"]
platforms = ["linux-64"]

[dependencies]
{chr(10).join(deps)}

[tasks]

[feature.dev.dependencies]
black = "*"
'''
    default_env = "[" + ", ".join(f'"{e}"' for e in envs) + "]"
    text += f'''
[environments]
default = {default_env}
'''
    return text


def run_command(cmd, check=True):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: Command failed with return code {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def check_pixi_installed():
    """Check if pixi is installed and available."""
    try:
        result = run_command(["pixi", "--version"], check=False)
        if result.returncode == 0:
            print(f"Found pixi: {result.stdout.strip()}")
            return True
        else:
            print("Error: pixi not found. This should not happen with fdp-installer.")
            sys.exit(1)
    except FileNotFoundError:
        print("Error: pixi not found. This should not happen with fdp-installer.")
        sys.exit(1)


def write_pixi_toml(latest=False, with_labeler=False, core_version=None):
    """Render pixi.toml into the current directory if it doesn't exist."""
    if not Path("pixi.toml").exists():
        Path("pixi.toml").write_text(
            render_pixi_toml(latest=latest, with_labeler=with_labeler,
                             core_version=core_version),
            encoding="utf-8",
        )
        print("Wrote pixi.toml to current directory")
    else:
        print("pixi.toml already exists in current directory")


def install_skills(target_dir):
    """Install Claude Code skills via the fdp CLI in the pixi environment."""
    print("Installing Claude Code skills...")
    result = subprocess.run(
        [
            "pixi", "run",
            "--manifest-path", str(target_dir / "pixi.toml"),
            "fdp", "skills", "install",
        ],
        text=True,
    )
    if result.returncode != 0:
        print("Warning: skill installation failed. Run 'fdp skills install' manually.")


def _print_device_selection_note():
    """Report which devices are available.

    fdp >= 0.5.0 composes all installed devices' environments and scopes
    per-command resolution by capability, so no selection is normally needed.
    """
    print(
        "\nThis environment includes multiple tokamaks (DIII-D 'd3d', "
        "MAST 'mast').\n"
        "No selection is required: `fdp env`/`fdp run` combine both, and\n"
        "`fdp ls`/`fdp login` pick the device that can service them.\n"
        "To pin one anyway:\n"
        "  - per command:  fdp --device d3d <subcommand> ...\n"
        "  - environment:  export FDP_DEFAULT_DEVICE=d3d\n"
        "  - persistent:   fdp device use d3d\n"
        "Run `fdp device list` to see what is installed."
    )


def install_fdp(target_dir, install_skills_flag=False,
                latest=False, with_labeler=False, core_version=None):
    """Install FDP in the specified directory."""
    print(f"Installing FDP in directory: {target_dir}")

    # Change to target directory
    original_dir = os.getcwd()
    os.chdir(target_dir)

    try:
        # Ensure pixi.toml is available
        write_pixi_toml(latest=latest, with_labeler=with_labeler,
                        core_version=core_version)

        # Install dependencies using pixi
        run_command(["pixi", "install", "-vv"])

        if install_skills_flag:
            install_skills(target_dir)
        else:
            print(
                "\nTo install Claude Code skills for FDP API assistance, run:\n"
                "  fdp skills install"
            )

        print("FDP installation completed")
        print(f"To activate the environment, run: cd {target_dir} && pixi shell")
        _print_device_selection_note()

    finally:
        # Return to original directory
        os.chdir(original_dir)


def _add_flavor_args(parser):
    parser.add_argument("--latest", action="store_true",
                        help="Use the rolling fdp-core-latest metapackage")
    parser.add_argument("--with-labeler", action="store_true",
                        help="Add ga-dfl-labeler (has a glibc <2.35 constraint)")
    parser.add_argument("--core-version", default=None,
                        help="Pin an exact fdp-core version instead of the newest")


def _add_install_args(parser):
    parser.add_argument(
        "--directory", "-d",
        default=".",
        help="Directory to install FDP in (default: current directory)"
    )
    parser.add_argument(
        "--install-skills", action="store_true",
        help="Also install Claude Code skills to ~/.claude/skills/"
    )
    parser.add_argument("--container", action="store_true",
                        help="Install the container-backed fdp shim instead of a "
                             "pixi environment (the default on macOS)")
    _add_flavor_args(parser)


def _pull(cmd):
    """Run an image pull; failures raise RuntimeError with a hint."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{cmd[0]} pull failed (exit {result.returncode}):\n"
            f"{result.stderr.strip()}\n\n"
            "If the container machine is not running: "
            "`podman machine start` or `colima start`.")


def install_container_mode(target_dir, *, core_version=None, runtime=None,
                           run=None, latest=None, has_image=None):
    """macOS path: write the shim to <target_dir>/bin/fdp and pull the image.

    `run` executes a command list (default: run_command, which exits on
    failure); `latest` resolves the newest blessed fdp-core (default: the
    channel).
    """
    target_dir = Path(target_dir)
    run = run or _pull
    latest = latest or channel.latest_core_version
    version = core_version or latest()
    image = f"{IMAGE_REPO}:{version}"

    if runtime is None:
        runtime = _shim_module.find_runtime(os.environ)

    if has_image is None:
        def has_image():
            return subprocess.run([runtime, "image", "inspect", image],
                                  capture_output=True).returncode == 0
    if has_image():
        print(f"{image} is already present; skipping pull")
    else:
        print(f"Pulling {image} with {runtime} ...")
        run([runtime, "pull", "--platform", "linux/amd64", image])

    bin_dir = target_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    source = Path(_shim_module.__file__).read_text(encoding="utf-8")
    if "__FDP_IMAGE__" not in source:
        raise RuntimeError("shim template has no __FDP_IMAGE__ placeholder")
    shim_path = bin_dir / "fdp"
    shim_path.write_text(source.replace("__FDP_IMAGE__", image), encoding="utf-8")
    shim_path.chmod(shim_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(
        f"\nFDP is installed as a container-backed command.\n"
        f"Add it to your PATH:\n\n"
        f"  export PATH=\"{bin_dir}:$PATH\"\n\n"
        f"Then `fdp login`, and `fdp run python script.py` runs inside\n"
        f"{image} with your current directory mounted. `fdp shell` opens a\n"
        f"shell inside the environment."
    )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "render":
        parser = argparse.ArgumentParser(
            prog="fdp-install render",
            description="Print the pixi.toml fdp-install would write")
        _add_flavor_args(parser)
        args = parser.parse_args(argv[1:])
        if args.latest and args.core_version:
            parser.error("--latest and --core-version are mutually exclusive")
        sys.stdout.write(render_pixi_toml(
            latest=args.latest, with_labeler=args.with_labeler,
            core_version=args.core_version))
        return

    parser = argparse.ArgumentParser(
        description="FDP Installer - Bootstrap script for Fusion Data Platform",
        epilog="Subcommand: `fdp-install render [--core-version X]` prints the "
               "pixi.toml an install would write.",
    )
    _add_install_args(parser)
    args = parser.parse_args(argv)
    if args.latest and args.core_version:
        parser.error("--latest and --core-version are mutually exclusive")

    container = args.container or sys.platform == "darwin"
    target_dir = Path(args.directory).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if container:
        if args.install_skills:
            parser.error("--install-skills does not apply to the container image; "
                         "run `fdp skills install` through the installed fdp")
        if args.latest or args.with_labeler:
            parser.error("--latest and --with-labeler do not apply to the container image")
        try:
            install_container_mode(target_dir, core_version=args.core_version)
        except (RuntimeError, _shim_module.ShimError) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
        return

    check_pixi_installed()
    install_fdp(
        target_dir,
        install_skills_flag=args.install_skills,
        latest=args.latest,
        with_labeler=args.with_labeler,
        core_version=args.core_version,
    )


if __name__ == "__main__":
    main()
