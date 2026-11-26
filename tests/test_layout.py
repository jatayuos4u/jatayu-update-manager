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

    def test_about_dialog_shows_creator_and_version(self):
        dialog = self.window.build_about_dialog()
        labels = dialog.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel)
        visible_text = ' '.join(label.text() for label in labels)
        self.assertIn('Anup Kumar Yadav', visible_text)
        from jatayu_update_manager import __version__
        self.assertIn(__version__.replace('rc', ' RC'), visible_text)
        dialog.close()

    def test_about_menu_localizes(self):
        self.assertEqual(self.window.about_action.text(), 'About')
        self.window.lang = 'hi'
        self.window.translate_ui()
        self.assertEqual(self.window.about_action.text(), 'परिचय')

    def test_desktop_icon_identity_and_packaged_svg(self):
        from pathlib import Path
        from jatayu_update_manager.main import DESKTOP_FILE_ID
        root = Path(__file__).resolve().parents[1]
        desktop = (root / 'assets/in.jatayuos.update-manager.desktop').read_text()
        svg = (root / 'assets/jatayu-update-manager.svg').read_text()
        rules = (root / 'debian/rules').read_text()
        self.assertEqual(DESKTOP_FILE_ID, 'in.jatayuos.update-manager')
        self.assertIn('Icon=jatayu-update-manager', desktop)
        self.assertIn('StartupWMClass=jatayu-update-manager', desktop)
        self.assertIn('viewBox="0 0 256 256"', svg)
        self.assertIn('usr/share/icons/hicolor/scalable/apps', rules)

    def test_untracked_transaction_diagnostic_does_not_modify_packages(self):
        from unittest.mock import patch
        self.window.settings.remove('supervised_transaction_id')
        with patch('jatayu_update_manager.main.read_status') as reader:
            text = self.window.supervised_status_text()
            reader.assert_not_called()
        self.assertIn('No supervised transaction', text)

    def test_interrupted_transaction_is_reported_as_unknown(self):
        from unittest.mock import patch
        self.window.settings.setValue('supervised_transaction_id', 'a' * 32)
        record = {'state': 'running', 'boot_id': 'a' * 36, 'exit_code': None}
        with patch('jatayu_update_manager.main.read_status', return_value=record), \
             patch('jatayu_update_manager.main.classify_status', return_value='interrupted_unknown'):
            text = self.window.supervised_status_text()
        self.assertIn('outcome is unknown', text)
        self.window.settings.remove('supervised_transaction_id')

    def test_corrupt_transaction_record_fails_closed(self):
        from unittest.mock import patch
        self.window.settings.setValue('supervised_transaction_id', 'a' * 32)
        with patch('jatayu_update_manager.main.read_status',
                   side_effect=ValueError('malformed')):
            text = self.window.supervised_status_text()
        self.assertIn('could not be verified', text)
        self.window.settings.remove('supervised_transaction_id')

    def test_transaction_status_menu_localizes(self):
        self.assertIn('Transaction status', self.window.transaction_status_action.text())
        self.window.lang = 'hi'
        self.window.translate_ui()
        self.assertIn('लेन-देन', self.window.transaction_status_action.text())

    def test_existing_transaction_recovers_tracking_at_startup(self):
        from unittest.mock import patch
        from jatayu_update_manager.main import MainWindow
        self.window.settings.setValue('supervised_transaction_id', 'a' * 32)
        self.window.settings.sync()
        with patch('jatayu_update_manager.main.read_status',
                   side_effect=FileNotFoundError):
            recovered = MainWindow()
            try:
                self.assertTrue(recovered.supervised_timer.isActive())
                self.assertEqual(recovered.settings.value('supervised_transaction_id'), 'a' * 32)
            finally:
                recovered.close()
                recovered.supervised_timer.stop()
        self.window.settings.remove('supervised_transaction_id')

    def test_status_menu_never_starts_apt(self):
        from unittest.mock import patch
        with patch('jatayu_update_manager.main.QMessageBox.information'), \
             patch.object(self.window, 'start_supervised_refresh') as launcher:
            self.window.show_transaction_status()
            launcher.assert_not_called()

    def test_experimental_start_is_disabled_without_opt_in(self):
        from unittest.mock import patch
        with patch('jatayu_update_manager.main.EXPERIMENTAL_SUPERVISED', False), \
             patch('jatayu_update_manager.main.QMessageBox.question') as question:
            self.window.start_supervised_refresh()
            question.assert_not_called()
