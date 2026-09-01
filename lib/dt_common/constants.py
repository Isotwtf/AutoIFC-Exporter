# -*- coding: utf-8 -*-
"""
Constants shared across the DigitalTwin extension.

Keeping the view-name prefix in one place means the "create views" tool
and the "export IFC" tool can never drift out of sync on how generated
views are identified.
"""

# Every view created by the "Create Views by Category" tool is named
# "Omniverse_<SafeCategoryName>" (optionally with a "_1", "_2", ...
# suffix to keep names unique). The "Export IFC by Category" tool
# detects its input views by this prefix.
DT_VIEW_PREFIX = "Omniverse_"

# Revit's CategoryType.Model flag covers more than physical building
# elements -- it also includes administrative/reference categories
# such as Sheets or Project Information, and a few categories (RVT
# Links, Rooms, Areas) that DO control real 3D geometry but aren't
# things this extension's category-isolation workflow is meant for.
# get_populated_model_categories() drops these by name after the
# "Model type + has placed elements + visibility-controllable in a 3D
# view" checks already filter out most of the noise. Edit this set to
# tune what the category picker shows (e.g. remove "Rooms" here if you
# later want Room/Space views for IFC space export).
EXCLUDED_CATEGORY_NAMES = {
    "Project Information",
    "Sheets",
    "Sheet Collections",
    "Viewports",
    "Materials",
    "Raster Images",
    "RVT Links",
    "Cameras",
    "Reference Planes",
    "Reference Lines",
    "Reference Points",
    "Survey Point",
    "Project Base Point",
    "Internal Origin",
    "Lines",
    "Grids",
    "Levels",
    "Legend Components",
    "Color Fill Legends",
    "Match Line",
    "Rooms",
    "Areas",
}
