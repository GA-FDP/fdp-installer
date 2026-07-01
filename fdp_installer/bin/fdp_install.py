#!/usr/bin/env python3
"""
FDP Installer - Bootstrap script for Fusion Data Platform installation
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path


_CMF_FEATURE = '''
# Opt-in provenance layer. cmflib is a PyPI git dep; ml-metadata is pip-only, so
# this MUST be a pixi feature -- it cannot live in the fdp-core conda metapackage.
[feature.cmf.dependencies]
python = "3.11.*"
protobuf = "<5"
attrs = "<24"
paramiko = "==3.4.1"
pathspec = "==0.12.1"
platformdirs = ">=3.1.1,<4"

[feature.cmf.pypi-dependencies]
cmflib = { git = "https://github.com/sammuli/cmf.git", branch = "fdp_installer_rebase" }
'''

_LABELER_DEP = 'ga-dfl-labeler = "==1.0.0"  # carries a glibc <2.35 constraint'


def render_pixi_toml(latest: bool = False, with_cmf: bool = False,
                     with_labeler: bool = False) -> str:
    core = "fdp-core-latest" if latest else "fdp-core"
    deps = [f'{core} = "*"']
    if with_labeler:
        deps.append(_LABELER_DEP)
    envs = ["dev"]
    if with_cmf:
        envs.append("cmf")
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
    if with_cmf:
        text += _CMF_FEATURE
    # The installer runs a plain `pixi install` (the default environment), so the
    # cmf feature must be activated in `default` for --with-cmf to take effect.
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


def write_pixi_toml(latest=False, with_cmf=False, with_labeler=False):
    """Render pixi.toml into the current directory if it doesn't exist."""
    if not Path("pixi.toml").exists():
        Path("pixi.toml").write_text(
            render_pixi_toml(latest=latest, with_cmf=with_cmf, with_labeler=with_labeler),
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


def install_fdp(target_dir, install_skills_flag=False,
                latest=False, with_cmf=False, with_labeler=False):
    """Install FDP in the specified directory."""
    print(f"Installing FDP in directory: {target_dir}")

    # Change to target directory
    original_dir = os.getcwd()
    os.chdir(target_dir)

    try:
        # Ensure pixi.toml is available
        write_pixi_toml(latest=latest, with_cmf=with_cmf, with_labeler=with_labeler)

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

    finally:
        # Return to original directory
        os.chdir(original_dir)


def main():
    parser = argparse.ArgumentParser(
        description="FDP Installer - Bootstrap script for Fusion Data Platform"
    )
    parser.add_argument(
        "--directory", "-d",
        default=".",
        help="Directory to install FDP in (default: current directory)"
    )
    parser.add_argument(
        "--install-skills", action="store_true",
        help="Also install Claude Code skills to ~/.claude/skills/"
    )
    parser.add_argument("--latest", action="store_true",
                        help="Use the rolling fdp-core-latest metapackage")
    parser.add_argument("--with-cmf", action="store_true",
                        help="Add the CMF provenance layer (pins Python 3.11)")
    parser.add_argument("--with-labeler", action="store_true",
                        help="Add ga-dfl-labeler (has a glibc <2.35 constraint)")

    args = parser.parse_args()

    # Check if pixi is installed (should always be available with fdp-installer)
    check_pixi_installed()

    # Create target directory if it doesn't exist
    target_dir = Path(args.directory).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    # Install FDP in the specified directory
    install_fdp(
        target_dir,
        install_skills_flag=args.install_skills,
        latest=args.latest,
        with_cmf=args.with_cmf,
        with_labeler=args.with_labeler,
    )


if __name__ == "__main__":
    main()
