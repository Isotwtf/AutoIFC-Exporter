# -*- coding: utf-8 -*-
"""
Renders a list of ExportResult as a table in the pyRevit output window
for the user running the export right now.
"""

CSV_HEADER = ["Category Name", "IFC File Name", "Status", "Duration (s)", "Message"]


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
