"""Find running StarCraft II processes without reading their launch arguments."""

import csv
import os
import subprocess
from pathlib import Path


def game_pids():
    names = {'sc2.exe', 'sc2_x64.exe'}
    if os.name == 'nt':
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq SC2*', '/FO', 'CSV', '/NH'],
                                    capture_output=True, text=True, timeout=10,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired as error:
            raise OSError('Could not check whether StarCraft II is running.') from error
        if result.returncode:
            raise OSError('Could not check whether StarCraft II is running.')
        return {int(row[1]) for row in csv.reader(result.stdout.splitlines())
                if len(row) >= 2 and row[0].casefold() in names and row[1].isdigit()}
    pids = set()
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            if path.read_text().strip().casefold() in names:
                pids.add(int(path.parent.name))
        except OSError:
            continue
    return pids


def game_running():
    return bool(game_pids())


def windows_process_path(pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                 wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # The process exited between the two checks.
            return None
        raise ctypes.WinError()
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise ctypes.WinError()
        return Path(buffer.value)
    finally:
        kernel.CloseHandle(handle)
