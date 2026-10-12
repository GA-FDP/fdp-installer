#!/bin/bash
# Activate the pixi environment baked into the image and run the FDP CLI.
# `shell` is not an fdp subcommand; it opens an interactive bash instead.
set -e
source /app/activate.sh
if [ "$1" = "shell" ]; then
    shift
    exec bash "$@"
fi
exec fdp "$@"
