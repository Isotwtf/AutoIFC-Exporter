# -*- coding: utf-8 -*-
"""
Compact branded result popup replacing pyrevit.forms.alert's generic
warning-triangle icon with an actual green checkmark (success) or red
X (failure), matching the same header/accent style as the other
custom windows in this extension.
"""
import os

import clr
clr.AddReference("PresentationFramework")

from pyrevit import forms
from System.Windows import Visibility

_XAML_PATH = os.path.join(os.path.dirname(__file__), "ResultWindow.xaml")


class ResultWindow(forms.WPFWindow):
    def __init__(self, success, title, message):
        forms.WPFWindow.__init__(self, _XAML_PATH)

        self.Title = title
        self.lblTitle.Text = title
        self.lblMessage.Text = message

        if success:
            self.iconCircleSuccess.Visibility = Visibility.Visible
            self.iconCheckPath.Visibility = Visibility.Visible
        else:
            self.iconCircleFail.Visibility = Visibility.Visible
            self.iconXPath1.Visibility = Visibility.Visible
            self.iconXPath2.Visibility = Visibility.Visible

        self.btnOk.Click += self._on_ok

    def _on_ok(self, sender, args):
        self.Close()


def show_result(success, title, message):
    """
    Show the branded result popup and block until the user clicks OK.
    """
    window = ResultWindow(success, title, message)
    window.ShowDialog()
