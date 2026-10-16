#!/usr/bin/env python3
"""
FDP Installer - Bootstrap script for Fusion Data Platform installation
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
import platform as _platform


_LABELER_DEP = 'ga-dfl-labeler = "==1.0.0"  # carries a glibc <2.35 constraint'

#: Platforms with native builds of every fdp-core member.
NATIVE_PLATFORMS = ("linux-64", "osx-arm64")

#: The first fdp-core whose every member installs on osx-arm64.
FIRST_OSX_ARM64_CORE = (1, 35, 0)


def host_platform(sys_platform=None, machine=None):
    """The conda subdir of this machine, or None where there is no native build."""
    sys_platform = sys.platform if sys_platform is None else sys_platform
    machine = _platform.machine() if machine is None else machine
    if sys_platform.startswith("linux") and machine in ("x86_64", "AMD64"):
        return "linux-64"
    if sys_platform == "darwin" and machine == "arm64":
        return "osx-arm64"
    return None


def _version_tuple(text):
    return tuple(int(p) for p in text.split(".")[:3] if p.isdigit())


def render_pixi_toml(latest: bool = False, with_labeler: bool = False,
                     core_version: "str | None" = None,
                     platform: str = "linux-64") -> str:
    if latest and core_version:
        raise ValueError("--latest and --core-version are mutually exclusive")
    if platform not in NATIVE_PLATFORMS:
        raise ValueError(f"no native FDP builds for {platform}")
    if with_labeler and platform != "linux-64":
        raise ValueError("--with-labeler is Linux-only (ga-dfl-labeler needs glibc)")
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
platforms = ["{platform}"]

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


def write_pixi_toml(latest=False, with_labeler=False, core_version=None,
                    platform="linux-64"):
    """Render pixi.toml into the current directory if it doesn't exist."""
    if not Path("pixi.toml").exists():
        Path("pixi.toml").write_text(
            render_pixi_toml(latest=latest, with_labeler=with_labeler,
                             core_version=core_version, platform=platform),
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
                latest=False, with_labeler=False, core_version=None,
                platform="linux-64"):
    """Install FDP in the specified directory."""
    print(f"Installing FDP in directory: {target_dir}")

    # Change to target directory
    original_dir = os.getcwd()
    os.chdir(target_dir)

    try:
        # Ensure pixi.toml is available
        write_pixi_toml(latest=latest, with_labeler=with_labeler,
                        core_version=core_version, platform=platform)

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
    _add_flavor_args(parser)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "render":
        parser = argparse.ArgumentParser(
            prog="fdp-install render",
            description="Print the pixi.toml fdp-install would write")
        _add_flavor_args(parser)
        parser.add_argument("--platform", choices=NATIVE_PLATFORMS,
                            default=host_platform() or "linux-64",
                            help="Platform to render for (default: this machine's)")
        args = parser.parse_args(argv[1:])
        try:
            text = render_pixi_toml(
                latest=args.latest, with_labeler=args.with_labeler,
                core_version=args.core_version, platform=args.platform)
        except ValueError as e:
            parser.error(str(e))
        sys.stdout.write(text)
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

    native = host_platform()
    if native is None:
        parser.error(
            f"no FDP build for this machine ({sys.platform}, {_platform.machine()}); "
            "supported platforms are Linux x86-64 and Apple Silicon Macs")
    target_dir = Path(args.directory).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    if native == "osx-arm64":
        if args.with_labeler:
            parser.error("--with-labeler is Linux-only (ga-dfl-labeler needs glibc)")
        if args.core_version and \
                _version_tuple(args.core_version) < FIRST_OSX_ARM64_CORE:
            parser.error(
                f"fdp-core {args.core_version} does not install on Apple Silicon; "
                f"the first that does is "
                f"{'.'.join(map(str, FIRST_OSX_ARM64_CORE))}.")

    check_pixi_installed()
    install_fdp(
        target_dir,
        install_skills_flag=args.install_skills,
        latest=args.latest,
        with_labeler=args.with_labeler,
        core_version=args.core_version,
        platform=native,
    )


if __name__ == "__main__":
    main()
