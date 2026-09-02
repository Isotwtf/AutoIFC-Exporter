# -*- coding: utf-8 -*-
"""
Defends against Revit's native IFC export engine popping up its own
dialogs mid-export without a properly set parent/owner window.

Confirmed case: exporting with a configuration whose Category Mapping
points at a named template (not "<In-Session Setup>") can make Revit
open its "Manage IFC Export Mapping Settings" window DURING
Document.Export() itself -- not during our "Configure Settings" step,
and not something IFCExportConfiguration.UpdateOptions() triggers (its
source has zero UI calls; confirmed by reading it). Since we're
driving export outside Revit's own command flow, that window isn't
owned by Revit's main window, so it can open behind it instead of on
top -- indistinguishable from a hang unless you go hunting for it with
Alt+Tab.

This module doesn't touch, dismiss, or auto-click anything (a hidden
dialog might need a real decision from the user -- guessing an answer
for them would be worse than a visible wait). It only uses standard
Win32 window APIs to detect any NEW top-level window our own process
creates while active, and bring it to the foreground so it's visible
immediately instead of requiring a manual hunt.
"""
import threading
import time

try:
    import ctypes
    from ctypes import wintypes
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _HAS_CTYPES = True
except Exception:
    _HAS_CTYPES = False

_SW_RESTORE = 9


def _enum_own_process_windows():
    """Return every top-level window handle owned by this process."""
    pid = _kernel32.GetCurrentProcessId()
    handles = []

    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd, _lparam):
        found_pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
        if found_pid.value == pid:
            handles.append(hwnd)
        return True

    _user32.EnumWindows(enum_proc_type(_callback), 0)
    return handles


class HiddenDialogWatcher(object):
    """
    Context manager: while active, polls for new top-level windows
    belonging to this process and brings each one to the foreground as
    soon as it appears. Use around any call that might block on a
    Revit-native dialog we don't control and can't guarantee is
    properly parented.

    Safe by construction: only acts on windows already confirmed to
    belong to OUR OWN process (matched by PID), only for the duration
    of the `with` block, and never sends input/clicks -- only window
    show/focus calls.
    """

    def __init__(self, poll_interval=0.3):
        self._poll_interval = poll_interval
        self._known_handles = set()
        self._stop_event = threading.Event()
        self._thread = None

    def __enter__(self):
        if not _HAS_CTYPES:
            return self
        try:
            self._known_handles = set(_enum_own_process_windows())
        except Exception:
            self._known_handles = set()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run)
        self._thread.daemon = True
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(2.0)
        return False

    def _run(self):
        while not self._stop_event.is_set():
            try:
                current = set(_enum_own_process_windows())
                for hwnd in current - self._known_handles:
                    try:
                        _user32.ShowWindow(hwnd, _SW_RESTORE)
                        _user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                self._known_handles = current
            except Exception:
                pass
            self._stop_event.wait(self._poll_interval)
