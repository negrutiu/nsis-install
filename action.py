import glob, os, re, subprocess, sys, time, winreg

def nsis_list(verbose=False):
    """
    List all NSIS installations found in the registry and default locations.
    Returns:
      List of unique installation directories.
    """
    installations = []

    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\NSIS"
    for registry in [
        {'hive': winreg.HKEY_LOCAL_MACHINE, 'hivename': "HKLM", 'view': winreg.KEY_WOW64_64KEY, 'verysilent': True},
        {'hive': winreg.HKEY_LOCAL_MACHINE, 'hivename': "HKLM", 'view': winreg.KEY_WOW64_32KEY, 'verysilent': False},
        {'hive': winreg.HKEY_CURRENT_USER,  'hivename': "HKCU", 'view': winreg.KEY_WOW64_64KEY, 'verysilent': True},
        {'hive': winreg.HKEY_CURRENT_USER,  'hivename': "HKCU", 'view': winreg.KEY_WOW64_32KEY, 'verysilent': True},
    ]:
        try:
            with winreg.OpenKey(registry['hive'], uninstall_key, access= winreg.KEY_READ|registry['view']) as regkey:
                instdir, regtype = winreg.QueryValueEx(regkey, "InstallLocation")
                winreg.CloseKey(regkey)
                instdir = os.path.normpath(os.path.expandvars(instdir))
                if os.path.exists(os.path.join(instdir, 'makensis.exe')):
                    if instdir not in installations:
                        installations.append(instdir)
                elif verbose:
                    print(f'-- "{instdir}" is invalid')
        except Exception as ex:
            if verbose and not registry['verysilent']:
                print(f'-- "{registry["hivename"]}\\{uninstall_key}" ({"wow64" if registry["view"] == winreg.KEY_WOW64_32KEY else "nativ"}): {ex}')

    for instdir in [r'%ProgramFiles%\NSIS', r'%ProgramFiles(x86)%\NSIS']:
        instdir = os.path.normpath(os.path.expandvars(instdir))
        if os.path.exists(os.path.join(instdir, 'makensis.exe')):
            if instdir not in installations:
                installations.append(instdir)
        elif verbose:
            print(f'-- "{instdir}" not found')

    return installations

def registry_path_remove(instdir, regroot, regpath, regvalue="Path"):
    """
    Remove all occurrences of a directory from a list of directories (`PATH`) stored in the registry.
    Returns:
      True if the registry was modified.
    """
    instdir = os.path.normpath(os.path.expandvars(instdir))
    if instdir == '': return False
    try:
        with winreg.OpenKey(regroot, regpath, access=winreg.KEY_READ|winreg.KEY_WRITE|winreg.KEY_WOW64_64KEY) as hkey:
            path, regtype = winreg.QueryValueEx(hkey, regvalue)
            paths = []
            modified = False
            for entry in path.split(os.pathsep):
                if os.path.normpath(os.path.expandvars(entry)) == instdir:
                    print(f'Removed "{entry}" from PATH')
                    modified = True
                else:
                    paths.append(entry)
            if modified:
                path = ''   # rebuild PATH
                for entry in paths:
                    path += (os.pathsep if path != "" else "") + entry
                winreg.SetValueEx(hkey, regvalue, 0, regtype, path)
            winreg.CloseKey(hkey)
            return modified
    except Exception as ex:
        print(f'-- registry_path_remove("{instdir}", "{regpath}"): {ex}')
    return False

def nsis_version(instdir):
    """ Query NSIS version by executing `makensis.exe /VERSION` in the specified installation directory. Returns `None` on error. """
    try:
        process = subprocess.Popen([os.path.join(instdir, 'makensis.exe'), '/VERSION'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cout, cerr = process.communicate()
        process.wait()
        if cout != None:
            for line in cout.decode('utf-8').split("\r\n"):
                # print(f"| {line}")
                if (matches := re.search(r'^v(\d+\.\d+(\.\d+(\.\d+)?)?)', line)) != None:   # look for "v1.2[.3[.4]]"
                    return matches.group(1)
    except Exception as ex:
        print(f'-- get_nsis_version("{instdir}"): {ex}')
    return None

def nsis_uninstall(instdir, unregister_path=True):
    """ Uninstall NSIS found in the specified installation directory. Returns uninstaller exit code or `-1` if NSIS not found. """
    if os.path.exists(os.path.join(instdir, 'Bin', 'makensis.exe')) and os.path.exists(uninst := os.path.join(instdir, 'uninst-nsis.exe')):
        print(f'Uninstall nsis/{nsis_version(instdir)} from "{instdir}" ...')
        exitcode = os.system(commandline := f'"{uninst}" /S _?={instdir}')
        print(f'| {commandline} : {exitcode}')
        if exitcode == 0:
            os.remove(uninst)
            os.rmdir(instdir)
            if unregister_path:
                registry_path_remove(instdir, winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", "Path")
                registry_path_remove(instdir, winreg.HKEY_CURRENT_USER, r"Environment", "Path")
        return exitcode
    print(f'-- uninstall_nsis("{instdir}") did not find NSIS')
    return -1

if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument("-u", "--uninstall", action='store_true', help='uninstall all NSIS installations')
    args = parser.parse_args()
    
    print(f'Arguments: {args.__dict__}')
    
    print(f'Python: {sys.version}')
    print(f'Platform: os.name="{os.name}", sys.platform="{sys.platform}"')

    for instdir in nsis_list():
        print(f'Found nsis/{nsis_version(instdir)} in "{instdir}"')
 
    if args.uninstall:
        count = 0
        for instdir in nsis_list(verbose=True):
            nsis_uninstall(instdir)
            count += 1
        if count == 0:
            print('No NSIS installations found to uninstall')