# -*- coding: utf-8 -*-
"""
Runs the actual per-view IFC export and records a structured result
for each attempt. Deliberately has zero pyrevit.forms / UI code so it
can be unit-exercised or reused from a batch/CLI context later.
"""
import time
import traceback

from Autodesk.Revit.DB import Transaction

from dt_common.ifc_setups import build_ifc_export_options
from dt_common.path_utils import make_safe_filename
from dt_common.window_watcher import HiddenDialogWatcher


class ExportResult(object):
    """One row of the final summary report."""

    def __init__(self, category_name, file_name, success, duration_seconds,
                 message=""):
        self.category_name = category_name
        self.file_name = file_name
        self.success = success
        self.duration_seconds = duration_seconds
        self.message = message

    @property
    def status_text(self):
        return "Success" if self.success else "Failed"


class IFCCategoryExporter(object):
    """
    Exports one IFC file per GeneratedCategoryView, isolating each
    export in its own try/except so one failing category can never
    stop the batch -- required when a project has hundreds of them.
    """

    def __init__(self, doc, setup, output_folder, on_progress=None):
        """
        doc            -- the active Document.
        setup          -- an IFCSetupInfo (see ifc_setups.py) shared by
                           every export in this run.
        output_folder  -- destination folder; must already exist.
        on_progress    -- optional callable(index, total, category_label)
                           invoked before each export starts, so the
                           caller can drive a UI progress bar / logger
                           without this class knowing about either.
        """
        self.doc = doc
        self.setup = setup
        self.output_folder = output_folder
        self.on_progress = on_progress

    def export_all(self, generated_views):
        """
        generated_views -- list of dt_common.view_utils.GeneratedCategoryView.
        Returns a list[ExportResult], one per input view, same order.
        """
        results = []
        total = len(generated_views)

        for index, gcv in enumerate(generated_views):
            if self.on_progress:
                self.on_progress(index, total, gcv.category_label)
            results.append(self._export_one(gcv))

        return results

    def _export_one(self, gcv):
        file_name = make_safe_filename(gcv.category_label, ".ifc")
        start_time = time.time()

        try:
            options = build_ifc_export_options(self.setup, gcv.view, self.doc)

            # Each category always exports to the same file name (e.g.
            # "Ducts.ifc") so re-running the export refreshes/overwrites
            # it in place -- the expected behavior for a repeatable
            # per-category export you run again as the model changes,
            # rather than piling up Ducts_1.ifc, Ducts_2.ifc, etc.
            #
            # Document.Export needs an open transaction on this Revit
            # version: it performs transient writes while applying
            # Category/Property Mapping templates, and Revit's
            # transaction-safety check enforces that regardless of
            # whether those writes end up being permanent model
            # changes. Older Revit versions didn't need this.
            transaction = Transaction(self.doc, "Export IFC - {}".format(gcv.category_label))
            transaction.Start()
            try:
                # Revit's native IFC export engine can pop up its own
                # dialog mid-export (confirmed: "Manage IFC Export
                # Mapping Settings" when the configuration references a
                # named Category Mapping template) without a properly
                # set owner window, since we're driving this outside
                # Revit's own command flow -- it can open hidden behind
                # the main window instead of on top. This just makes
                # sure any such window is visible; see window_watcher.py.
                with HiddenDialogWatcher():
                    export_succeeded = self.doc.Export(self.output_folder, file_name, options)
                transaction.Commit()
            except Exception:
                if transaction.HasStarted() and not transaction.HasEnded():
                    transaction.RollBack()
                raise

            if not export_succeeded:
                raise RuntimeError("Document.Export returned False (export did not complete).")

            duration = time.time() - start_time
            return ExportResult(
                category_name=gcv.category_label,
                file_name=file_name,
                success=True,
                duration_seconds=duration,
                message="OK",
            )

        except Exception as ex:
            duration = time.time() - start_time
            return ExportResult(
                category_name=gcv.category_label,
                file_name=file_name,
                success=False,
                duration_seconds=duration,
                message="{}: {}".format(ex, traceback.format_exc(limit=1)),
            )
