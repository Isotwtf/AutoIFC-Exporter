# -*- coding: utf-8 -*-
"""
Defends against Revit's native IFC exporter losing track of its own
windows because we're driving it outside its normal, fully-wired
command flow (where every window it creates is properly owned by
Revit's main window, so Windows always keeps them sensibly stacked).

Two confirmed symptoms of the same root cause:

1. Exporting with a configuration whose Category Mapping points at a
   named template can make Revit's native export engine open its own
   "Manage IFC Export Mapping Settings" window DURING Document.Export()
   itself -- not something IFCExportConfiguration.UpdateOptions()
   triggers (its source has zero UI calls; confirmed by reading it),
   so it's coming from deeper inside Revit's own export engine. That
   window opens unowned, so it can appear behind Revit's main window
   instead of on top -- indistinguishable from a hang unless you go
   hunting for it with Alt+Tab.
2. Opening a file picker from inside our reflectively-shown "Modify
   Setup" editor (e.g. "Import setup...") can cause THAT editor window
   itself to minimize/drop behind other applications entirely, again
   because it isn't owned by anything Windows considers its parent.

This module doesn't touch, dismiss, or auto-click any dialog's content
(a hidden dialog might need a real decision from the user -- guessing
an answer for them would be worse than a visible wait). It only uses
standard Win32 window APIs to:
  - bring any NEW top-level window our own process creates to the
    foreground as soon as it appears (case 1), and
  - un-minimize (but NOT force-focus, so we don't steal focus from a
    legitimately active child dialog like a file picker) one specific
    "protected" window if Windows minimizes it while we're watching
    (case 2).
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
    Context manager: while active, polls (every poll_interval seconds)
    for new top-level windows belonging to this process and brings
    each one to the foreground as soon as it appears. If protect_hwnd
    is given, also un-minimizes that specific window if it gets
    minimized -- without forcing focus onto it, so an active child
    dialog (e.g. a file picker) never loses focus as a side effect.

    Use around any call that might block on a Revit-native window we
    don't control and can't guarantee is properly parented.

    Safe by construction: only acts on windows already confirmed to
    belong to OUR OWN process (matched by PID) or explicitly passed in
    as protect_hwnd, only for the duration of the `with` block, and
    never sends input/clicks -- only window show/restore/focus calls.
    """

    def __init__(self, protect_hwnd=None, poll_interval=0.3):
        self._protect_hwnd = protect_hwnd
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

                if self._protect_hwnd:
                    try:
                        if _user32.IsIconic(self._protect_hwnd):
                            _user32.ShowWindow(self._protect_hwnd, _SW_RESTORE)
                    except Exception:
                        pass
            except Exception:
                pass
            self._stop_event.wait(self._poll_interval)
