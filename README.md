# GitHub action `negrutiu/nsis-install`

[![GitHub Marketplace](https://img.shields.io/badge/Marketplace-GitHub%20Actions-blue?logo=github)](https://github.com/marketplace/actions/nsis-install)

This GitHub action installs [negrutiu/nsis](https://github.com/negrutiu/nsis), a fork of the [official NSIS](https://nsis.sourceforge.io) (Nullsoft Scriptable Install System) Windows installer system.

Compared to the official NSIS releases, this fork includes a few additions:
- Builds native `amd64` installers (in addition to `x86`)
- Adds some useful plugins (e.g. `NScurl`, `TaskbarProgress`, and more)

The fork comes in two architectures: `x86` and `amd64`. Both of them can build both `x86` and `amd64` installers.  
The `x86` version will replace the official NSIS installation that is pre-installed on GitHub Windows runners.

The action downloads and installs the [latest build](https://github.com/negrutiu/nsis/releases/latest) from GitHub.

> [!WARNING]
> This action only works on Windows runners.


# Action Inputs

### `arch`

NSIS compiler architecture to install.  
Both x86 and amd64 compilers are able to build both x86 and amd64 installers. 

Accepted values:
- `x86`, `Win32`, `i[2-6]86`
- `amd64`, `x64`, `x86(-|_)64`

All values are internally normalized to `x86` or `amd64`  

Default is `x86` which will replace the official NSIS installation that is pre-installed on GitHub Windows runners.

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
              uses: negrutiu/nsis-install@v1

            - name: Build installer
              run: makensis my_installer.nsi
```

## Action Outputs

You can use action outputs to get installation details.  
First thing, give an `id` to the action step...

```yaml
jobs:
    build:
        runs-on: windows-latest
        steps:
            - name: Checkout code
              uses: actions/checkout@v4

            - name: Install or upgrade NSIS
              id: nsis
              uses: negrutiu/nsis-install@v1

            - name: Show NSIS info
              run: |
                echo "NSIS dir: ${{ steps.nsis.outputs.instdir }}"
                echo "NSIS version: ${{ steps.nsis.outputs.version }}"
                echo "NSIS arch: ${{ steps.nsis.outputs.arch }}"

            - name: Build installer
              run: makensis my_installer.nsi
```

## Native `amd64` Installers

Use `Target` directive in your NSIS script to build for different architectures.

```nsis
; NSIS installer
!define /ifndef ARCH "x86"
Target "${ARCH}-unicode"  ; possible values: amd64-unicode, x86-unicode, x86-ansi (deprecated)

; Optionally set output file name based on architecture
OutFile "my_installer_${ARCH}.exe"

; ... rest of script ...
```

In your workflow, specify `ARCH` as command line argument when invoking `makensis`.
```yaml
jobs:
    build:
        runs-on: windows-latest
        steps:
            - uses: actions/checkout@v4

            - name: Install NSIS
              uses: negrutiu/nsis-install@v1

            - name: Build x86 installer
              run: makensis /DARCH=x86 my_installer.nsi

            - name: Build amd64 installer
              run: makensis /DARCH=amd64 my_installer.nsi
```
