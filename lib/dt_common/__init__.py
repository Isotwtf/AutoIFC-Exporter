# -*- coding: utf-8 -*-
"""
dt_common
=========
Shared library for the DigitalTwin pyRevit extension.

Modules in this package are imported by multiple pushbuttons (the
"Create Views by Category" tool and the "Export IFC by Category" tool),
so keep them UI-agnostic: no forms.* calls here, only Revit API /
filesystem logic. UI orchestration belongs in each button's script.py.
"""
