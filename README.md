# GitHub action `negrutiu/nsis-install`

[![Static Badge](https://img.shields.io/badge/GitHub%20Marketplace-negrutiu%2Fnsis--install-blue?style=flat-square&logo=github)
](https://github.com/marketplace/actions/install-nsis-compiler)

This GitHub action installs or upgrades the __NSIS compiler__ (Nullsoft Scriptable Install System) on GitHub Windows runners.

You can choose between two NSIS distributions:
- The [negrutiu-NSIS](https://github.com/negrutiu/nsis) fork (default)
- The [official NSIS](https://nsis.sourceforge.io) release

Compared to the official NSIS releases, the negrutiu-NSIS fork can build native `amd64` installers and comes with some useful plugins pre-installed.

This GitHub action downloads and installs the latest build of the selected distribution. If NSIS is already installed, it will be upgraded to the latest version.

> [!WARNING]
> This action only works on Windows runners.


# Action Inputs

### distro

NSIS distribution to install:

- `negrutiu` - Installs the latest build of the [negrutiu-NSIS](https://github.com/negrutiu/nsis) fork
- `official` - Installs the latest release of the [official NSIS](https://nsis.sourceforge.io)

Default is `negrutiu`

### `arch`

NSIS compiler architecture to install:
- `x86`, `Win32`, `i[2-6]86`   - Available in all distros
- `amd64`, `x64`, `x86(-|_)64` - Only available in the `negrutiu` distro

All values are internally normalized to `x86` or `amd64`  
Default is `x86` which will replace the official NSIS installation that is pre-installed on GitHub Windows runners. If you opt for the `negrutiu` distro, both `x86` and `amd64` compilers can build both `x86` and `amd64` installers.

> [!IMPORTANT]
> `arm64` is not supported.

### `install-dir`

Custom directory to install NSIS to.  

Defaults to `%ProgramFiles%\NSIS` or `%ProgramFiles(x86)%\NSIS` depending on the architecture.

> [!NOTE]
> If the specified directory is invalid (e.g., due to insufficient permissions, a non-existent drive, or other filesystem errors), the installer will fall back to the default location. You can check the action output `instdir` to see the actual installation directory.

### `register-path`

Adds NSIS install directory to the system `PATH` environment variable.

Defaults to `true`.


# Action Outputs

### `instdir`
Installation directory (e.g. `C:\Program Files (x86)\NSIS`)

### `version`
Installed NSIS version (e.g. `1.2.3.4`)

### `arch`
Installed NSIS architecture (`x86` or `amd64`)


# Usage

## Basic

```yaml
jobs:
  build:
    runs-on: windows-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Install NSIS
      uses: negrutiu/nsis-install@v2

    - name: Build installer
      run: makensis my_installer.nsi
```

## Read Outputs

You can use action outputs to get installation details.  
First thing, give an `id` to the action step...

```yaml
jobs:
  build:
    runs-on: windows-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Install NSIS
      id: nsis
      uses: negrutiu/nsis-install@v2

    - name: Show NSIS info
      run: |
        echo "NSIS dir: ${{ steps.nsis.outputs.instdir }}"
        echo "NSIS version: ${{ steps.nsis.outputs.version }}"
        echo "NSIS arch: ${{ steps.nsis.outputs.arch }}"

    - name: Build installer
      run: makensis my_installer.nsi
```

## Native `amd64` Installers

To build for `amd64`, use `Target amd64-unicode` directive in your NSIS script.

```nsis
; --------------------
; my_installer.nsi
; --------------------

!define /ifndef ARCH "x86"
Target "${ARCH}-unicode"  ; possible values: amd64-unicode, x86-unicode, x86-ansi

OutFile "my_installer_${ARCH}.exe"

; [...]
```

In your workflow, use `-D` makensis option to define the `ARCH` variable.
```yaml
jobs:
  build:
    runs-on: windows-latest
    steps:
    - Name: Checkout code
      uses: actions/checkout@v4

    - name: Install NSIS
      uses: negrutiu/nsis-install@v2

    - name: Build x86 installer
      run: makensis -DARCH=x86 my_installer.nsi

    - name: Build amd64 installer
      run: makensis -DARCH=amd64 my_installer.nsi
```

# Related topics

- To install or upgrade [NSIS plugins](https://nsis.sourceforge.io/Category:Plugins) on your GitHub runner, check out [negrutiu/nsis-install-plugin](https://github.com/marketplace/actions/install-nsis-plugin) in the Marketplace.