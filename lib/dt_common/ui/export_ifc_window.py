# -*- coding: utf-8 -*-
"""
Custom WPF window for "Export IFC by Category": combines category
selection, IFC Export Setup configuration (via Revit's own native
"Modify Setup" editor), and output folder selection into a single
screen, replacing the previous sequence of separate popups.
"""
import os

import clr
clr.AddReference("PresentationFramework")

from pyrevit import forms
from System.Windows import Visibility
from System.Windows.Controls import CheckBox

from dt_common.ifc_setups import get_ifc_export_setups, open_setup_editor, IFCSetupInfo

_XAML_PATH = os.path.join(os.path.dirname(__file__), "ExportIFCWindow.xaml")


class ExportIFCWindow(forms.WPFWindow):
    def __init__(self, doc, category_labels):
        forms.WPFWindow.__init__(self, _XAML_PATH)

        self.doc = doc
        self.diagnostics = []
        self.selected_categories = []
        self.chosen_setup = None
        self.output_folder = None

        self._checkboxes = []
        self._setups = []
        self._used_native_setups = False
        self._config_map = None

        self.lblCategoryHeader.Text = "Categories ({} generated views found)".format(
            len(category_labels)
        )

        for label in sorted(category_labels):
            checkbox = CheckBox()
            checkbox.Content = label
            checkbox.IsChecked = True
            checkbox.Click += self._on_checkbox_click
            self.categoryPanel.Children.Add(checkbox)
            self._checkboxes.append(checkbox)

        self.txtSearch.TextChanged += self._on_search_changed
        self.btnCheckAll.Click += self._on_check_all
        self.btnUncheckAll.Click += self._on_uncheck_all
        self.btnConfigureSetup.Click += self._on_configure_setup
        self.btnBrowseFolder.Click += self._on_browse_folder
        self.btnCancel.Click += self._on_cancel
        self.btnConfirm.Click += self._on_confirm

        self._update_selected_count()
        self._load_default_setup()

    # -- IFC export setup --------------------------------------------

    def _load_default_setup(self):
        setups, used_native, diagnostics, config_map = get_ifc_export_setups(self.doc)
        self.diagnostics.extend(diagnostics)
        self._setups = setups
        self._used_native_setups = used_native
        self._config_map = config_map

        if not used_native:
            # Revit only loads the component that stores named IFC
            # Export Setups into memory after its own File > Export >
            # IFC dialog has run at least once in this session.
            diagnostics_text = "\n".join("- {}".format(line) for line in diagnostics)
            forms.alert(
                "Your project's named IFC Export Setups aren't available in "
                "this Revit session, so only generic IFC versions are shown "
                "below (not your project's real setups).\n\n"
                "If you haven't yet: open File > Export > IFC once (Cancel "
                "out, no need to export), then reopen this tool.\n\n"
                "Detection log for this run:\n{}".format(diagnostics_text),
                title="Native IFC Setups Not Loaded Yet",
            )

        if setups:
            self.chosen_setup = setups[0]
            self.lblCurrentSetup.Text = "Using: {}".format(self.chosen_setup.name)
        else:
            self.lblCurrentSetup.Text = "No IFC export setups are available in this project."

    def _on_configure_setup(self, sender, args):
        if not self._used_native_setups or self._config_map is None:
            forms.alert(
                "Revit's native settings editor isn't available in this "
                "session (no named IFC Export Setups could be read) -- "
                "using the generic IFC version list instead.",
                title="Configure Settings",
            )
            return

        starting_name = self.chosen_setup.name if self.chosen_setup else self._setups[0].name
        edited = open_setup_editor(self._config_map, starting_name, self.doc, self.diagnostics)
        if edited is not None:
            self.chosen_setup = IFCSetupInfo(edited.Name, configuration=edited)
            self.lblCurrentSetup.Text = "Using: {}".format(self.chosen_setup.name)

    # -- output folder -------------------------------------------------

    def _on_browse_folder(self, sender, args):
        folder = forms.pick_folder(title="Select Output Folder for IFC Files")
        if folder:
            self.output_folder = folder
            self.txtOutputFolder.Text = folder

    # -- category checklist ---------------------------------------------

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

    # -- confirm / cancel -------------------------------------------------

    def _on_cancel(self, sender, args):
        self.DialogResult = False
        self.Close()

    def _on_confirm(self, sender, args):
        selected = [cb.Content for cb in self._checkboxes if cb.IsChecked]
        if not selected:
            forms.alert("Select at least one category to export.", title="Export IFC by Category")
            return
        if self.chosen_setup is None:
            forms.alert("No IFC export setup is available.", title="Export IFC by Category")
            return
        if not self.output_folder:
            forms.alert("Choose an output folder first.", title="Export IFC by Category")
            return

        self.selected_categories = selected
        self.DialogResult = True
        self.Close()


def show_export_configuration(doc, category_labels):
    """
    Show the combined category / IFC setup / output folder
    configuration window.

    Returns (selected_categories, chosen_setup, output_folder,
    diagnostics). The first three are None if the user cancelled;
    diagnostics is always the accumulated setup-detection log, useful
    for troubleshooting regardless of outcome.
    """
    window = ExportIFCWindow(doc, category_labels)
    window.ShowDialog()
    if not window.DialogResult:
        return None, None, None, window.diagnostics
    return (
        window.selected_categories,
        window.chosen_setup,
        window.output_folder,
        window.diagnostics,
    )
