# -*- coding: utf-8 -*-
"""
Create one 3D view per selected category.
Each view will show only the chosen category and its subcategories.

Views are named after the category itself (e.g. "Ducts"). The
"Export IFC by Category" tool finds these views afterward via an
Extensible Storage tag (dt_common.view_tag), not by name -- so the
view name is free to be exactly the category name with no prefix.
"""
from pyrevit import forms, script, revit
from Autodesk.Revit.DB import *
import traceback

from dt_common.path_utils import make_safe_token
from dt_common.category_utils import get_populated_model_categories
from dt_common.ui.create_views_window import show_category_selection
from dt_common.view_tag import tag_view_with_category

doc = revit.doc

# 1. Gather model categories that actually have elements placed in
#    this document (skips the ~300 built-in Revit categories that
#    don't apply here, e.g. infrastructure-only categories in a
#    building model).
doc_categories = get_populated_model_categories(doc)

# Fallback if none found
if not doc_categories:
    forms.alert("No populated model categories found in this project.")
    script.exit()

available_categories = sorted(list(doc_categories.keys()))

# 2. Let the user pick categories via the custom window (search,
#    checklist pre-checked since every entry is already known to be
#    used in the model, check-all/uncheck-all, live selection count).
selected_names = show_category_selection(available_categories)

if not selected_names:
    script.exit()

# 3. Find 3D ViewFamilyType
vft_3d = None
for vft in FilteredElementCollector(doc).OfClass(ViewFamilyType):
    if vft.ViewFamily == ViewFamily.ThreeDimensional:
        vft_3d = vft
        break

if not vft_3d:
    forms.alert("No 3D ViewFamilyType found in project.")
    script.exit()

created_views = []


def make_view_name(category_name):
    return make_safe_token(category_name)


# 4. Create one view per selected category
for sel_name in selected_names:
    # resolve category object (case sensitive first, fallback case-insensitive)
    cat = doc_categories.get(sel_name)
    if cat is None:
        for c in doc.Settings.Categories:
            try:
                if c.Name.lower() == sel_name.lower() and c.CategoryType == CategoryType.Model:
                    cat = c
                    break
            except:
                pass
    if cat is None:
        forms.alert("Category not found in this project: {}".format(sel_name))
        continue

    # create view in a transaction
    t = Transaction(doc, "Create 3D view for '{}'".format(sel_name))
    try:
        t.Start()

        view = View3D.CreateIsometric(doc, vft_3d.Id)

        # unique, safe name
        base_name = make_view_name(cat.Name)
        unique_name = base_name
        idx = 1
        existing_names = {v.Name for v in FilteredElementCollector(doc).OfClass(View3D)}
        while unique_name in existing_names:
            unique_name = "{}_{}".format(base_name, idx)
            idx += 1

        view.Name = unique_name

        # Tag with the exact category name (not the sanitized view
        # name) so "Export IFC by Category" can find and label this
        # view correctly regardless of what it's named.
        tag_view_with_category(view, cat.Name)

        # Make sure a view template doesn't override visibility settings
        try:
            view.ViewTemplateId = ElementId.InvalidElementId
        except:
            pass

        # Hide every category (best-effort)
        for c in doc.Settings.Categories:
            try:
                view.SetCategoryHidden(c.Id, True)
                # hide subcategories too
                try:
                    for sub in c.SubCategories:
                        try:
                            view.SetCategoryHidden(sub.Id, True)
                        except:
                            pass
                except:
                    pass
            except:
                pass

        # Show the selected category and its subcategories
        try:
            view.SetCategoryHidden(cat.Id, False)
        except:
            pass
        try:
            for sub in cat.SubCategories:
                try:
                    view.SetCategoryHidden(sub.Id, False)
                except:
                    pass
        except:
            pass

        # Hide Revit Links and Imports to avoid extra geometry showing
        try:
            view.SetCategoryHidden(ElementId(BuiltInCategory.OST_RvtLinks), True)
        except:
            pass
        try:
            view.SetCategoryHidden(ElementId(BuiltInCategory.OST_ImportInstance), True)
        except:
            pass

        # Also hide RevitLinkInstance elements if present
        try:
            link_instances = FilteredElementCollector(doc).OfClass(RevitLinkInstance).ToElements()
            if link_instances:
                link_ids = [li.Id for li in link_instances]
                try:
                    view.HideElements(link_ids)
                except:
                    for lid in link_ids:
                        try:
                            view.HideElements([lid])
                        except:
                            pass
        except:
            pass

        t.Commit()
        created_views.append(unique_name)

    except Exception as ex:
        try:
            t.RollBack()
        except:
            pass
        forms.alert("Failed to create view for '{}':\n{}\n\n{}".format(sel_name, ex, traceback.format_exc()))

# 5. Report results
if created_views:
    forms.alert("Created {} view(s):\n\n{}".format(len(created_views), "\n".join(created_views)))
else:
    forms.alert("No views were created.")
