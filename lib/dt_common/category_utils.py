# -*- coding: utf-8 -*-
"""
Category discovery for the "Create Views by Category" picker.

Revit's Settings.Categories always lists every built-in category
(walls, doors, ... but also things like Abutments or Bridge Decks that
only apply to infrastructure projects) whether or not the current
model actually uses it. On top of that, CategoryType.Model itself is
broader than "physical building/MEP element" -- it also covers
administrative categories like Sheets and Project Information. This
module narrows the raw category list down to what the category-view
workflow actually needs: categories that (1) have elements placed in
this document, (2) can actually be shown/hidden in a 3D view, and
(3) aren't in the explicit exclusion list for the handful of
categories that pass both checks but still aren't meaningful here
(RVT Links, Rooms, Areas -- see constants.EXCLUDED_CATEGORY_NAMES).
"""
from Autodesk.Revit.DB import CategoryType, FilteredElementCollector, View3D

from dt_common.constants import EXCLUDED_CATEGORY_NAMES


def _find_reference_3d_view(doc):
    """
    Any existing, non-template View3D works as the reference for
    Category.get_AllowsVisibilityControl() -- that check only depends
    on the view's type/family, not its current content or camera.
    Returns None if the project has no 3D view yet, in which case the
    visibility-control check is skipped by the caller.
    """
    for view in FilteredElementCollector(doc).OfClass(View3D):
        if not view.IsTemplate:
            return view
    return None


def get_populated_model_categories(doc):
    """
    Return {category_name: Category} for every category that is a
    real, currently-used, isolatable-in-3D building/MEP category.

    Uses FirstElement() per category rather than counting all matches,
    so this stays fast even when scanning hundreds of categories --
    OfCategoryId is a quick/indexed filter, so each check is cheap and
    short-circuits on the first hit.
    """
    reference_view = _find_reference_3d_view(doc)
    populated = {}

    for cat in doc.Settings.Categories:
        try:
            if cat.CategoryType != CategoryType.Model:
                continue
            if cat.Name in EXCLUDED_CATEGORY_NAMES:
                continue

            if reference_view is not None:
                try:
                    if not cat.get_AllowsVisibilityControl(reference_view):
                        continue
                except Exception:
                    # Categories that don't support this query at all
                    # are almost always non-graphical/administrative
                    # ones -- treat as "not applicable to 3D views".
                    continue

            has_elements = (
                FilteredElementCollector(doc)
                .OfCategoryId(cat.Id)
                .WhereElementIsNotElementType()
                .FirstElement()
                is not None
            )
            if has_elements:
                populated[cat.Name] = cat
        except Exception:
            # A handful of built-in categories can't be queried this
            # way (e.g. internal/reserved ones) -- skip rather than
            # fail the whole tool over one category.
            pass

    return populated
