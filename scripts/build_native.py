"""Compile the checked-in adapter using an x64 MSVC developer shell."""
import argparse
from pathlib import Path
import shutil
import subprocess

from generate_profile import ADAPTERS, adapter_paths, generate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dll', required=True, type=Path)
    parser.add_argument('--platform', choices=ADAPTERS, default='steam')
    args = parser.parse_args()
    if not shutil.which('cl'):
        raise SystemExit('Run in an x64 Native Tools Command Prompt for Visual Studio (cl.exe required).')
    prefix, engine = adapter_paths(args.platform)
    generate(args.reference_dll, args.platform)
    out = ROOT / 'build' / (prefix + 'native')
    out.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / 'native').iterdir():
        if path.suffix in {'.h', '.cpp', '.manifest'}:
            shutil.copy2(path, out / path.name)
    shutil.copy2(ROOT / 'private' / (prefix + 'native') / 'engine_compat_profile.h', out / 'engine_compat_profile.h')
    if shutil.which('mt'):
        link_args = ['/link', '/INCREMENTAL:NO', '/MANIFEST:EMBED', '/MANIFESTINPUT:host.manifest', 'user32.lib']
    else:
        link_args = ['/link', '/INCREMENTAL:NO', '/MANIFEST:NO', 'user32.lib']
    subprocess.run(['cl', '/nologo', '/O2', '/EHsc', '/std:c++17', 'desktop_host.cpp',
                    '/Fe:FM27Simulator.exe', '/Fo:desktop_host.obj', *link_args], cwd=out, check=True)
    if not shutil.which('mt'):
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.BeginUpdateResourceW.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
        k32.BeginUpdateResourceW.restype = wintypes.HANDLE
        k32.UpdateResourceW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p, wintypes.DWORD]
        k32.UpdateResourceW.restype = wintypes.BOOL
        k32.EndUpdateResourceW.argtypes = [wintypes.HANDLE, wintypes.BOOL]
        k32.EndUpdateResourceW.restype = wintypes.BOOL
        manifest_bytes = (out / 'host.manifest').read_bytes()
        h = k32.BeginUpdateResourceW(str(out / 'FM27Simulator.exe'), False)
        if not h or not k32.UpdateResourceW(h, ctypes.c_void_p(24), ctypes.c_void_p(1), 0, manifest_bytes, len(manifest_bytes)) or not k32.EndUpdateResourceW(h, False):
            raise OSError(f'Failed to embed host.manifest (win32={ctypes.get_last_error()})')
    dest = engine / 'fm27_native'
    shutil.copy2(out / 'FM27Simulator.exe', dest / 'FM27Simulator.exe')
    shutil.copy2(ROOT / 'native' / (prefix + 'adapter_version.json'), dest / 'adapter_version.json')
    print('Built', dest / 'FM27Simulator.exe')


if __name__ == '__main__':
    main()
