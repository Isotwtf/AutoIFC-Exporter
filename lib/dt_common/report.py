# -*- coding: utf-8 -*-
"""
Turns a list of ExportResult into: a CSV file on disk (for archiving /
feeding other tools) and a table printed to the pyRevit output window
(for the user running the export right now).
"""
import codecs
import os

from dt_common.constants import REPORT_SUBFOLDER
from dt_common.path_utils import ensure_folder_exists, unique_path


CSV_HEADER = ["Category Name", "IFC File Name", "Status", "Duration (s)", "Message"]


def write_csv_report(results, output_folder, run_timestamp):
    """
    Write the summary as CSV into <output_folder>/_ExportReports and
    return the full path written to.
    """
    report_folder = ensure_folder_exists(
        os.path.join(output_folder, REPORT_SUBFOLDER)
    )
    file_name = "IFC_Export_Report_{}.csv".format(run_timestamp)
    report_path = unique_path(report_folder, file_name)

    with codecs.open(report_path, "w", encoding="utf-8-sig") as f:
        f.write(",".join(CSV_HEADER) + "\n")
        for r in results:
            row = [
                _csv_escape(r.category_name),
                _csv_escape(r.file_name),
                r.status_text,
                "{:.2f}".format(r.duration_seconds),
                _csv_escape(r.message),
            ]
            f.write(",".join(row) + "\n")

    return report_path


def _csv_escape(value):
    value = "" if value is None else str(value)
    if any(ch in value for ch in (",", '"', "\n")):
        value = '"{}"'.format(value.replace('"', '""'))
    return value


def print_summary_table(output, results):
    """
    Render the summary as a table in the pyRevit output window.
    `output` is the object returned by pyrevit.script.get_output().
    """
    table_data = [
        [r.category_name, r.file_name, r.status_text,
         "{:.2f}".format(r.duration_seconds), r.message]
        for r in results
    ]
    output.print_table(
        table_data=table_data,
        title="IFC Export Summary",
        columns=CSV_HEADER,
    )

    succeeded = sum(1 for r in results if r.success)
    failed = len(results) - succeeded
    total_duration = sum(r.duration_seconds for r in results)

    output.print_md(
        "**Total:** {} categories | **Success:** {} | **Failed:** {} | "
        "**Total time:** {:.1f}s".format(
            len(results), succeeded, failed, total_duration
        )
    )
