# Fusion Data Platform Installer

The Fusion Data Platform uses pixi to manage its various package dependencies. The simplest way to get set up is to first install the ```fdp-installer``` conda package and the run the ```fdp-install``` script.

Note that for the instructions below you can substitute ```mamba``` or ```micromamba``` for ```conda```, depending on your local setup.

Here's the procedure:

```
conda create -c ga-fdp -c conda-forge -n fdp-installer fdp-installer
```
Note that the ```-n``` argument is arbitrary. You can name the installer environment whatever you want.

```
conda activate fdp-installer # or whatever you names the install environment
```

## Install in current directory

```
fdp-install
```

## Install in a specific directory

```
fdp-install --directory /path/to/project
# or
fdp-install -d /path/to/project
```

The installer will:
1. Create the specified directory if it doesn't exist
2. Copy the pixi.toml configuration file 
3. Install all conda and pip dependencies using pixi
4. Set up the FDP environment

To activate the environment after installation:
```
cd /path/to/project
pixi shell
```

## macOS

On an Apple Silicon Mac `fdp-install` builds a native pixi environment, exactly
as on Linux:

    fdp-install -d ~/fdp
    cd ~/fdp && pixi shell
    fdp login

This needs fdp-core 1.35.0 or newer (the first whose every package has an
Apple Silicon build); `--with-labeler` is Linux-only.

Intel Macs and ARM Linux are not supported.

Full guide: https://ga-fdp.github.io/macos/

## Developing the installer itself

The distribution mechanism for the installer is as a conda package. To build the package,
just go to ```fdp-installer/conda-recipe``` and run

```
rattler-build build
``` 




