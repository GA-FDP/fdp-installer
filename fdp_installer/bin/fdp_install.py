#!/usr/bin/env python3
"""
FDP Installer - Bootstrap script for Fusion Data Platform installation
"""

import argparse
import subprocess
import sys
import os
import shutil
from pathlib import Path

# Bundled pixi.toml lives alongside this script's parent package
_BUNDLED_PIXI_TOML = Path(__file__).resolve().parent.parent / "pixi.toml"


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


def copy_pixi_toml():
    """Copy pixi.toml from package to current directory if it doesn't exist."""
    if not Path("pixi.toml").exists():
        if not _BUNDLED_PIXI_TOML.is_file():
            print(f"Error: bundled pixi.toml not found at {_BUNDLED_PIXI_TOML}")
            sys.exit(1)
        shutil.copy2(_BUNDLED_PIXI_TOML, "pixi.toml")
        print("Copied pixi.toml to current directory")
    else:
        print("pixi.toml already exists in current directory")


def install_fdp(target_dir):
    """Install FDP in the specified directory."""
    print(f"Installing FDP in directory: {target_dir}")
    
    # Change to target directory
    original_dir = os.getcwd()
    os.chdir(target_dir)
    
    try:
        # Ensure pixi.toml is available
        copy_pixi_toml()
        
        # Install dependencies using pixi
        run_command(["pixi", "install", "-vv"])
        
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
    
    args = parser.parse_args()
    
    # Check if pixi is installed (should always be available with fdp-installer)
    check_pixi_installed()
    
    # Create target directory if it doesn't exist
    target_dir = Path(args.directory).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Install FDP in the specified directory
    install_fdp(target_dir)


if __name__ == "__main__":
    main()
