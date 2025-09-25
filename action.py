import ctypes, datetime, os, re, shutil, subprocess, struct, sys, winreg
from urllib import request

import ssl
from pip._vendor import certifi     # use pip certifi to fix (urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1123)>)


# GitHub Actions sets RUNNER_DEBUG=1 when debug logging is enabled
if verbose := (os.environ.get("RUNNER_DEBUG", default="0") == "1"):
    print(f'GitHub debug logging enabled (RUNNER_DEBUG=1)')
    print(f'Python: {sys.version}')
    print(f'Platform: os.name="{os.name}", sys.platform="{sys.platform}"')


def broadcast_settings_change(param=None):
    """ Broadcast `WM_SETTINGCHANGE` to all windows to notify them of environment changes. """
    HWND_BROADCAST = 0xFFFF
    WM_SETTINGCHANGE = 0x001A
    try:
        result = ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, param)
        if verbose: print(f'SendMessage(HWND_BROADCAST, WM_SETTINGCHANGE, {param}) = {result}')
    except Exception as ex:
        print(f"-- WM_SETTINGCHANGE broadcast: {ex}")


def path_add(pathlist, path, keep_existing=True, front=True):
    """ Add a directory to a `PATH` string. """
    path = os.path.normpath(path)

    paths = []
    for entry in pathlist.split(os.pathsep):
        if os.path.normpath(os.path.expandvars(entry)).casefold() == path.casefold():
            if keep_existing:
                return (False, pathlist)   # already exists
        else:
            paths.append(entry)

    pathlist = ''   # rebuild PATH
    for entry in paths:
        pathlist += (os.pathsep if pathlist != "" else "") + entry

    if front:
        pathlist = path + (os.pathsep if pathlist != "" else "") + pathlist
    else:
        pathlist = pathlist + (os.pathsep if pathlist != "" else "") + path

    return (True, pathlist)

def path_remove(pathlist, path):
    """ Remove directory (all occurrences) from `PATH` string. """
    path = os.path.normpath(os.path.expandvars(path))

    modified = False
    paths = []
    for entry in pathlist.split(os.pathsep):
        if os.path.normpath(os.path.expandvars(entry)).casefold() == path.casefold():
            modified = True
        else:
            paths.append(entry)

    if modified:
        pathlist = ''   # rebuild PATH
        for entry in paths:
            pathlist += (os.pathsep if pathlist != "" else "") + entry

    return (modified, pathlist)

def registry_path_add(instdir, regroot, regpath, regvalue="Path", keep_existing=True, front=True):
    """ Add a directory to a `PATH` string stored in the registry. """
    modified = False
    path = None
    try:
        regtype = winreg.REG_EXPAND_SZ
        with winreg.OpenKey(regroot, regpath, access=winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as hkey:
            path, regtype = winreg.QueryValueEx(hkey, regvalue)
        modified, path = path_add(path, instdir, keep_existing, front)
        if modified:
            with winreg.OpenKey(regroot, regpath, access=winreg.KEY_WRITE|winreg.KEY_WOW64_64KEY) as hkey:
                winreg.SetValueEx(hkey, regvalue, 0, regtype, path)
                print(f'Added "{instdir}" to {"user" if regroot == winreg.HKEY_CURRENT_USER else "system"} PATH')
                broadcast_settings_change('Environment')
    except Exception as ex:
        modified = False
        print(f'-- registry_path_add("{instdir}", "{regpath}"): {ex}')
    return (modified, path)

def registry_path_remove(instdir, regroot, regpath, regvalue="Path"):
    """ Remove directory (all occurrences) from a `PATH` string stored in the registry. """
    modified = False
    path = None
    try:
        regtype = winreg.REG_EXPAND_SZ
        with winreg.OpenKey(regroot, regpath, access=winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as hkey:
            path, regtype = winreg.QueryValueEx(hkey, regvalue)
        modified, path = path_remove(path, instdir)
        if modified:
            with winreg.OpenKey(regroot, regpath, access=winreg.KEY_WRITE|winreg.KEY_WOW64_64KEY) as hkey:
                winreg.SetValueEx(hkey, regvalue, 0, regtype, path)
                print(f'Removed "{instdir}" from {"user" if regroot == winreg.HKEY_CURRENT_USER else "system"} PATH')
                broadcast_settings_change('Environment')
    except Exception as ex:
        modified = False
        print(f'-- registry_path_remove("{instdir}", "{regpath}"): {ex}')
    return (modified, path)

def process_path_add(instdir, keep_existing=True, front=True):
    """ Add directory to `os.environ['PATH']`. """
    modified, path = path_add(os.environ.get('PATH', ''), instdir, keep_existing, front)
    if modified:
        os.environ['PATH'] = path
        print(f'Added "{instdir}" to process PATH')
    return (modified, path)

def process_path_remove(instdir):
    """ Remove directory (all occurrences) from `os.environ['PATH']`. """
    modified, path = path_remove(os.environ.get('PATH', ''), instdir)
    if modified:
        os.environ['PATH'] = path
        print(f'Removed "{instdir}" from process PATH')
    return (modified, path)

def github_path_add(instdir):
    if (github_path := os.getenv('GITHUB_PATH')) is not None:
        try:
            with open(github_path, 'a') as fo:
                fo.write(f'{instdir}\n')
                print(f'Added "{instdir}" to GITHUB_PATH')
            return True
        except Exception as ex:
            print(f'-- github_path_add("{instdir}"): {ex}')
    return False


def download_github_asset(owner, repo, tag, name_regex, token, outdir):
    """
    Download a GitHub release asset matching the specified regex.
    Returns the path to the downloaded file.
    """
    if tag.lower() == 'latest':
        url = f'https://api.github.com/repos/{owner}/{repo}/releases/latest'
    else:
        url = f'https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}'

    asset_url = None
    asset_size = None
    asset_path = None

    t0 = datetime.datetime.now()
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    http_request = request.Request(url)
    http_request.add_header('Accept', 'application/vnd.github.v3+json')
    if token:
        http_request.add_header('Authorization', f'Bearer {token}')
        if verbose: print(f'Info: Found valid GitHub token ({len(token)} chars)')
    else:
        print('Warning: No GitHub token provided, may run into API rate limits')
    with request.urlopen(http_request, context=ssl_context) as http:
        import json
        response_json = json.loads(http.read().decode('utf-8'))
        print(f'GET {url} --> {http.status} {http.reason}, {int((datetime.datetime.now()-t0).total_seconds()*1000)} ms')
        if verbose:
            print(f'    Request headers {http_request.header_items()}')
            print(f'    Response headers {http.getheaders()}')
            for asset in response_json['assets']:
                print(f'> asset: "{asset["name"]}", {asset["size"]} bytes, {asset["browser_download_url"]}')
        for asset in response_json['assets']:
            if 'name' in asset and re.match(name_regex, asset['name'], re.IGNORECASE):
                asset_url = asset['browser_download_url']
                asset_size = asset['size']
                asset_path = os.path.join(outdir, asset['name'])
                break

    if asset_url is None:
        raise ValueError(f'No asset matching "{name_regex}"')

    if os.path.exists(asset_path) and os.path.getsize(asset_path) == asset_size:
        print(f'Reuse existing "{asset_path}"')
        return asset_path

    t0 = datetime.datetime.now()
    http_request = request.Request(asset_url)
    http_request.add_header('Accept', 'application/octet-stream')
    if token:
        http_request.add_header('Authorization', f'Bearer {token}')
    with request.urlopen(http_request, context=ssl_context) as http:
        if not os.path.exists(outdir):
            os.makedirs(outdir, exist_ok=True)
        with open(asset_path, 'wb') as file:
            shutil.copyfileobj(http, file)
            print(f'GET {asset_url} --> {http.status} {http.reason}, {int((datetime.datetime.now()-t0).total_seconds()*1000)} ms')
            if verbose:
                print(f'    Request headers: {http_request.header_items()}')
                print(f'    Response headers: {http.getheaders()}')
        return asset_path


def pe_architecture(path):
    """ Return the architecture of a PE file (`x86`, `amd64`, `arm64`). """
    with open(path, "rb") as fi:
        # Read DOS header to get e_lfanew (offset to PE header)
        fi.seek(0x3C)
        data = fi.read(4)
        if len(data) != 4:
            raise ValueError("Not a valid PE file (cannot read e_lfanew).")
        (e_lfanew,) = struct.unpack("<I", data)

        # Read PE signature + COFF header (at e_lfanew)
        fi.seek(e_lfanew)
        sig = fi.read(4)
        if sig != b"PE\x00\x00":
            raise ValueError("PE signature not found.")

        coff = fi.read(20)  # IMAGE_FILE_HEADER is 20 bytes
        if len(coff) != 20:
            raise ValueError("Truncated COFF header.")
        (machine,) = struct.unpack("<H", coff[:2])

        # https://learn.microsoft.com/en-us/windows/win32/sysinfo/image-file-machine-constants
        machines = {0x014c: 'x86', 0x8664: 'amd64', 0xaa64: 'arm64', 0x0200: 'ia64'}
        return machines.get(machine, None)
    return None


def nsis_version(instdir):
    """ Query NSIS version by executing `makensis.exe /VERSION` in the specified installation directory. Returns `None` on error. """
    try:
        process = subprocess.Popen([os.path.join(instdir if instdir is not None else '', 'makensis.exe'), '/VERSION'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cout, cerr = process.communicate()
        process.wait()
        if cout != None:
            for line in cout.decode('utf-8').split("\r\n"):
                if (matches := re.search(r'^v(\d+\.\d+(\.\d+(\.\d+)?)?)', line)) != None:   # look for "v1.2[.3[.4]]"
                    return matches.group(1)
    except Exception as ex:
        print(f'-- get_nsis_version("{instdir}"): {ex}')
    return None


def nsis_list():
    """
    List all NSIS installations found in the registry and default locations.
    Returns:
      List of unique installation directories.
    """
    installations = []

    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\NSIS"
    for registry in [
        {'hive': winreg.HKEY_LOCAL_MACHINE, 'hivename': "HKLM", 'view': winreg.KEY_WOW64_64KEY},
        {'hive': winreg.HKEY_LOCAL_MACHINE, 'hivename': "HKLM", 'view': winreg.KEY_WOW64_32KEY},
        {'hive': winreg.HKEY_CURRENT_USER,  'hivename': "HKCU", 'view': winreg.KEY_WOW64_64KEY},
        {'hive': winreg.HKEY_CURRENT_USER,  'hivename': "HKCU", 'view': winreg.KEY_WOW64_32KEY},
        ]:
        try:
            with winreg.OpenKey(registry['hive'], uninstall_key, access= winreg.KEY_READ|registry['view']) as regkey:
                if verbose: print(f'>> "{registry["hivename"]}\\{uninstall_key}" ({"wow64" if registry["view"] == winreg.KEY_WOW64_32KEY else "nativ"}): found')
                instdir, regtype = winreg.QueryValueEx(regkey, "InstallLocation")
                winreg.CloseKey(regkey)
                instdir = os.path.normpath(os.path.expandvars(instdir))
                if os.path.exists(os.path.join(instdir, 'makensis.exe')):
                    if instdir not in installations:
                        installations.append(instdir)
                else:
                    if verbose: print(f'-- "{instdir}" has an invalid/corrupted NSIS installation')
        except Exception as ex:
            if verbose: print(f'-- "{registry["hivename"]}\\{uninstall_key}" ({"wow64" if registry["view"] == winreg.KEY_WOW64_32KEY else "nativ"}): {ex}')

    for instdir in [r'%ProgramFiles%\NSIS', r'%ProgramFiles(x86)%\NSIS']:
        instdir = os.path.normpath(os.path.expandvars(instdir))
        if os.path.exists(os.path.join(instdir, 'makensis.exe')):
            if verbose: print(f'>> "{instdir}" found')
            if instdir not in installations:
                installations.append(instdir)
        else:
            if verbose: print(f'-- "{instdir}" not found')

    return installations


def nsis_install(arch, instdir=None, tempdir=os.path.expandvars('%temp%'), register_path=True):
    """ Download and install the latest [negrutiu/nsis](https://github.com/negrutiu/nsis) release.
        Returns:
            `(instdir, version, arch)` or raises on error. """
    # normalize architecture
    finalarch = None
    matrix = {'x86': ['x86', 'win32', 'i[3-6]86'], 'amd64': ['amd64', 'x86(_|-)64', 'x64']}
    for name, values in matrix.items():
        for value in values:
            if re.match(rf'^{value}$', arch, re.IGNORECASE):
                finalarch = name
    if finalarch:
        arch = finalarch
    else:
        raise ValueError(f'-- unsupported architecture "{arch}"')

    # download
    github_token = None
    installer = download_github_asset('negrutiu', 'nsis', 'latest', rf'nsis-.*-{arch}\.exe', github_token, tempdir)
    version = re.search(rf'nsis-(.+)-.*-{arch}\.exe', os.path.basename(installer)).group(1)   # "nsis-3.11.7461.288-negrutiu-x86.exe" => "3.11.7461.288"
    assert version, f'-- failed to parse version from "{installer}"'

    # install
    commandline = f'"{installer}" /S'
    if instdir is not None and instdir != '':
        commandline += f' /D={os.path.normpath(os.path.expandvars(instdir))}'
    exitcode = os.system(commandline)
    print(f'Run {commandline} : {exitcode}')
    if exitcode != 0:
        raise RuntimeError(f'-- {installer} returned {exitcode}')

    out_instdir = instdir
    if out_instdir is not None and (out_instdir == '' or not os.path.exists(out_instdir)):
        out_instdir = None
    if out_instdir is None:
        out_instdir = os.path.normpath(os.path.expandvars(r'%ProgramFiles%\NSIS' if arch == 'amd64' else r'%ProgramFiles(x86)%\NSIS'))

    if register_path:
        github_path_add(out_instdir)
        process_path_add(out_instdir)
        registry_path_add(out_instdir, winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "Path")
        # registry_path_add(instdir2, winreg.HKEY_CURRENT_USER, r"Environment", "Path")  # HKLM is enough
    else:
        if verbose: print(f'PATH entries left intact')

    # verify
    pe = 'makensis.exe'
    version2 = nsis_version('')     # makensis.exe in PATH
    if verbose: print(f'Verify version("{pe}") == {version} : {"PASS" if version2 == version else "FAIL"}')
    if version2 != version:
        raise RuntimeError(f'-- "{pe}" version mismatch, expected "{version}", got "{version2}"')

    pe = os.path.join(out_instdir, 'makensis.exe')
    out_version = nsis_version(out_instdir)
    if verbose: print(f'Verify version("{pe}") == {version} : {"PASS" if out_version == version else "FAIL"}')
    if out_version != version:
        raise RuntimeError(f'-- "{pe}" version mismatch, expected "{version}", got "{out_version}"')

    arch2 = pe_architecture(pe)
    if verbose: print(f'Verify arch("{pe}") == "{arch}" : {"PASS" if arch2 == arch else "FAIL"}')
    if arch2 != arch:
        raise RuntimeError(f'-- "{pe}" architecture mismatch, expected {hex(arch)}, got {hex(arch2)}')

    for target in ['x86-unicode', 'amd64-unicode', 'x86-ansi']:
        for plugin in ['NScurl.dll']:
            pe = os.path.join(out_instdir, 'Plugins', target, plugin)
            if verbose: print(f'Verify exists("{pe}") : {"PASS" if os.path.exists(pe) else "FAIL"}')
            if not os.path.exists(pe):
                raise RuntimeError(f'-- "{pe}" is missing after installation')

    return (out_instdir, out_version, arch)


def nsis_uninstall(instdir, unregister_path=True):
    """ Uninstall NSIS found in the specified installation directory. Returns uninstaller exit code or `-1` if NSIS not found. """
    if os.path.exists(os.path.join(instdir, 'Bin', 'makensis.exe')) and os.path.exists(uninst := os.path.join(instdir, 'uninst-nsis.exe')):
        exitcode = os.system(commandline := f'"{uninst}" /S _?={instdir}')
        print(f'Run {commandline} : {exitcode}')
        if exitcode == 0:
            os.remove(uninst)
            os.rmdir(instdir)
            if unregister_path:
                process_path_remove(instdir)
                registry_path_remove(instdir, winreg.HKEY_CURRENT_USER, r"Environment", "Path")
                registry_path_remove(instdir, winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "Path")
            else:
                if verbose: print(f'PATH entries left intact')
        return exitcode
    print(f'-- uninstall_nsis("{instdir}") did not find NSIS')
    return -1


if __name__ == '__main__':

    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-a", "--arch", type=str, default='x86', help='NSIS architecture (install only). Supported values: x86, Win32, i386, i486, i586, i686, amd64, x64, x86_64. All values are converted to "x86" or "amd64"')
    parser.add_argument("-d", "--dir", type=str, help='NSIS custom installation directory (install only)')
    parser.add_argument("-i", "--install", action='store_true', help='install NSIS')
    parser.add_argument("-u", "--uninstall", action='store_true', help='uninstall all NSIS installations')
    parser.add_argument("-v", "--verbose", action='store_true', help='more verbose output')
    args = parser.parse_args()

    print(f'Arguments: {args.__dict__}')

    if args.verbose:
        verbose = True

    for instdir in (list := nsis_list()):
        print(f'Found nsis/{pe_architecture(os.path.join(instdir, "makensis.exe"))}/{nsis_version(instdir)} in "{instdir}"')
    if not list:
        print('No NSIS installations found')

    if args.uninstall:
        for instdir in (list := nsis_list()):
            nsis_uninstall(instdir)
        if not list:
            print('No NSIS installations found to uninstall')

    if args.install:
        nsis_install(args.arch, args.dir)
