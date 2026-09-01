# -*- coding: utf-8 -*-
"""
Custom WPF window for "Create Views by Category": a single screen
(search + checklist + check-all/uncheck-all + count) replacing the
plain pyrevit.forms.SelectFromList popup.
"""
import os

import clr
clr.AddReference("PresentationFramework")

from pyrevit import forms
from System.Windows import Visibility
from System.Windows.Controls import CheckBox

_XAML_PATH = os.path.join(os.path.dirname(__file__), "CreateViewsWindow.xaml")


class CreateViewsWindow(forms.WPFWindow):
    def __init__(self, category_names):
        forms.WPFWindow.__init__(self, _XAML_PATH)

        self._checkboxes = []
        self.selected_categories = []

        self.lblCategoryHeader.Text = "Categories ({} found in model)".format(len(category_names))

        for name in sorted(category_names):
            checkbox = CheckBox()
            checkbox.Content = name
            checkbox.IsChecked = True
            checkbox.Click += self._on_checkbox_click
            self.categoryPanel.Children.Add(checkbox)
            self._checkboxes.append(checkbox)

        self.txtSearch.TextChanged += self._on_search_changed
        self.btnCheckAll.Click += self._on_check_all
        self.btnUncheckAll.Click += self._on_uncheck_all
        self.btnCancel.Click += self._on_cancel
        self.btnConfirm.Click += self._on_confirm

        self._update_selected_count()

    def _visible_checkboxes(self):
        return [cb for cb in self._checkboxes if cb.Visibility == Visibility.Visible]

    def _update_selected_count(self):
        total = len(self._checkboxes)
        checked = sum(1 for cb in self._checkboxes if cb.IsChecked)
        self.lblSelectedCount.Text = "{} of {} selected".format(checked, total)

    def _on_checkbox_click(self, sender, args):
        self._update_selected_count()

    def _on_search_changed(self, sender, args):
        query = (self.txtSearch.Text or "").strip().lower()
        for cb in self._checkboxes:
            name = cb.Content
            cb.Visibility = (
                Visibility.Visible
                if (not query or query in name.lower())
                else Visibility.Collapsed
            )

    def _on_check_all(self, sender, args):
        for cb in self._visible_checkboxes():
            cb.IsChecked = True
        self._update_selected_count()

    def _on_uncheck_all(self, sender, args):
        for cb in self._visible_checkboxes():
            cb.IsChecked = False
        self._update_selected_count()

    def _on_cancel(self, sender, args):
        self.selected_categories = []
        self.DialogResult = False
        self.Close()

    def _on_confirm(self, sender, args):
        selected = [cb.Content for cb in self._checkboxes if cb.IsChecked]
        if not selected:
            forms.alert("Select at least one category first.", title="Create Views by Category")
            return
        self.selected_categories = selected
        self.DialogResult = True
        self.Close()


def show_category_selection(category_names):
    """
    Show the category-selection window. Returns the list of selected
    category names, or None if the user cancelled.
    """
    window = CreateViewsWindow(category_names)
    window.ShowDialog()
    if not window.DialogResult:
        return None
    return window.selected_categories
