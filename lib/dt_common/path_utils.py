# -*- coding: utf-8 -*-
"""
Filesystem helpers: turning arbitrary Revit names into safe file/view
names, and making sure output folders exist before we write into them.
"""
import os
import re

_INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')


def make_safe_token(name, fallback="Unnamed"):
    """
    Collapse any run of whitespace/invalid characters into a single
    underscore so the result is safe to use as both a Revit element
    name and a Windows file name.
    """
    if not name:
        return fallback
    token = re.sub(r'\W+', '_', name).strip('_')
    return token or fallback


def make_safe_filename(name, extension, fallback="Unnamed"):
    """
    Build a Windows-safe file name (without touching the extension).
    Unlike make_safe_token this only strips characters Windows
    forbids in file names, so spaces and readability are preserved.
    """
    base = (name or "").strip() or fallback
    base = _INVALID_CHARS_RE.sub("_", base)
    base = base.rstrip(" .")  # Windows disallows trailing dots/spaces
    if not base:
        base = fallback
    if not extension.startswith("."):
        extension = "." + extension
    return base + extension


def ensure_folder_exists(folder_path):
    """Create folder_path (and parents) if it does not already exist."""
    if folder_path and not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    return folder_path
