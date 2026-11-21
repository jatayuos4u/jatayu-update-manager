"""Headless Qt layout smoke test for the expandable update list."""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtWidgets import QApplication
from jatayu_update_manager.main import MainWindow


class UpdateListLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.rows = [
            ('fonts-opensymbol', '1.0', '2.0'),
            ('libreoffice-core', '24.0', '25.0'),
        ]
        self.cache_patch = patch('jatayu_update_manager.main.available_updates',
                                 return_value=self.rows)
        self.history_patch = patch('jatayu_update_manager.main.recent_history',
                                   return_value='')
        self.cache_patch.start()
        self.history_patch.start()
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        self.cache_patch.stop()
        self.history_patch.stop()

    def test_list_is_expandable_and_restorable(self):
        self.assertTrue(self.window.summary_panel.isVisibleTo(self.window))
        self.window.list_focus_button.setChecked(True)
        self.assertFalse(self.window.summary_panel.isVisibleTo(self.window))
        self.assertEqual(self.window.tabs.currentIndex(), 0)
        self.window.list_focus_button.setChecked(False)
        self.assertFalse(self.window.summary_panel.isHidden())
        self.assertEqual(self.window.table.rowCount(), 2)

    def test_package_versions_have_full_tooltips(self):
        self.assertEqual(self.window.table.item(0, 1).toolTip(), '1.0')
        self.assertEqual(self.window.table.item(0, 2).toolTip(), '2.0')

    def test_focus_button_localizes(self):
        self.window.lang = 'hi'
        self.window.translate_ui()
        self.assertEqual(self.window.list_focus_button.text(), 'अपडेट सूची बड़ी करें')
        self.window.list_focus_button.setChecked(True)
        self.assertEqual(self.window.list_focus_button.text(), 'डैशबोर्ड दिखाएँ')
