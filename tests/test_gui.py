"""Offscreen regression tests; no privileged helper or network calls."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    import ryoku_proxy as ui
except ImportError:
    ui = None

@unittest.skipIf(ui is None, 'PySide6 is not installed')
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(ui.STYLES)

    def setUp(self):
        profile = ui.new_profile('Test <b>profile</b>')
        profile['host'] = 'proxy.example'
        store = {'version': 2, 'active_id': None, 'profiles': [profile]}
        for item in (patch.object(ui, 'load_store', return_value=store),
                     patch.object(ui.Window, 'run_job'),
                     patch.object(ui.QSystemTrayIcon, 'isSystemTrayAvailable', return_value=False)):
            item.start()
            self.addCleanup(item.stop)
        self.window = ui.Window()
        self.addCleanup(self.window.deleteLater)
        for timer in (self.window.t_status, self.window.t_snapshot, self.window.t_health):
            timer.stop()

    def test_refresh_keeps_list_items_and_tray_actions(self):
        item = self.window.profile_list.item(0)
        action = self.window.tray_menu.actions()[0]
        self.window.refresh_ui()
        self.assertIs(self.window.profile_list.item(0), item)
        self.assertIs(self.window.tray_menu.actions()[0], action)

    def test_missing_tun_resets_rates(self):
        self.window.tun_rx = 1234
        self.window.tun_tx = 5678
        self.window.last_counters = {'timestamp': 1}
        self.window.job_finished('snapshot', True, {'tun': None}, '')
        self.assertEqual((self.window.tun_rx, self.window.tun_tx), (0, 0))
        self.assertIsNone(self.window.last_counters)

    def test_background_poll_keeps_diagnostic_result(self):
        self.window.status_line.setText('TLS/CONNECT: 42 ms')
        self.window.job_finished('snapshot', True, {'tun': None}, '')
        self.assertEqual(self.window.status_line.text(), 'TLS/CONNECT: 42 ms')

    def test_profile_name_is_plain_text(self):
        self.assertEqual(self.window.primary_profile.textFormat(), Qt.TextFormat.PlainText)

    def test_all_pages_at_narrow_size(self):
        self.window.resize(800, 650)
        self.window.show()
        for index in range(len(self.window.NAV_KEYS)):
            self.window.show_page(index)
            self.app.processEvents()
            self.assertEqual(self.window.pages.currentIndex(), index)
        self.window.hide()

    def test_exit_waits_for_existing_jobs(self):
        self.window.jobs['snapshot'] = object()
        with patch.object(self.app, 'quit') as quit_app:
            self.window.quit_gui()
            self.assertTrue(self.window.exiting)
            quit_app.assert_not_called()
            self.window.worker_stopped('snapshot')
            quit_app.assert_called_once()
