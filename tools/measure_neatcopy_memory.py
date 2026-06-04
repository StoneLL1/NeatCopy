"""Memory measurement helper for NeatCopy performance optimization.

Usage:
    python tools/measure_neatcopy_memory.py [repo_path]

Reports baseline and post-import Working Set / Private Memory in MB.
"""
import ctypes
import gc
import os
import sys
from ctypes import wintypes


class PMCEX(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('PageFaultCount', wintypes.DWORD),
        ('PeakWorkingSetSize', ctypes.c_size_t),
        ('WorkingSetSize', ctypes.c_size_t),
        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPagedPoolUsage', ctypes.c_size_t),
        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
        ('PagefileUsage', ctypes.c_size_t),
        ('PeakPagefileUsage', ctypes.c_size_t),
        ('PrivateUsage', ctypes.c_size_t),
    ]


GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
GetCurrentProcess.restype = wintypes.HANDLE
GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMCEX), wintypes.DWORD]
GetProcessMemoryInfo.restype = wintypes.BOOL


def memory_mb():
    gc.collect()
    counters = PMCEX()
    counters.cb = ctypes.sizeof(counters)
    GetProcessMemoryInfo(GetCurrentProcess(), ctypes.byref(counters), counters.cb)
    return counters.WorkingSetSize / 1024 / 1024, counters.PrivateUsage / 1024 / 1024


def report(label):
    ws, private = memory_mb()
    print(f"{label}|WS={ws:.1f}MB|Private={private:.1f}MB")


if __name__ == '__main__':
    repo = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, os.path.join(repo, 'src'))

    report("baseline")
    import main
    report("import main")
