# Fusion Data Platform Installer

To install the FDP:

```
conda install -c ga-fdp fdp-installer
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






