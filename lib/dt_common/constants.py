# -*- coding: utf-8 -*-
"""
Constants shared across the DigitalTwin extension.
"""

# Revit's CategoryType.Model flag covers more than physical building
# elements -- it also includes administrative/reference categories
# such as Sheets or Project Information, and a handful of categories
# (RVT Links, Rooms, Areas, Point Clouds, Detail Items) that DO control
# real, placed 3D geometry but aren't things this extension's
# category-isolation workflow is meant for (scan/reference data,
# view-specific 2D components, spatial boundaries -- not physical
# elements worth their own IFC entity). get_populated_model_categories()
# drops these by name after the "Model type + has placed elements +
# visibility-controllable in a 3D view" checks already filter out most
# of the noise. Edit this set to tune what the category picker shows
# (e.g. remove "Rooms" here if you later want Room/Space views for IFC
# space export).
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
    "Point Clouds",
    "Detail Items",
}
