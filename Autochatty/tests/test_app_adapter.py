import unittest
from unittest.mock import patch

import app_adapter as app


class AppAdapterTests(unittest.TestCase):
    def test_app_window_identification(self):
        self.assertTrue(app.allowed_window('ChatGPT', 'ChatGPT.exe'))
        self.assertTrue(app.allowed_window('ChatGPT - Work', 'codex.exe'))
        self.assertFalse(app.allowed_window('ChatGPT', 'msedge.exe'))
        self.assertFalse(app.allowed_window('Mi app ChatGPT', 'ChatGPT.exe'))
        self.assertFalse(app.allowed_window('Controlador ChatGPT v3 - Aplicacion Windows', 'pythonw.exe'))

    def test_ambiguous_chat_never_clicked(self):
        with patch.object(app, '_sidebar_candidates', return_value=[object(), object()]), \
             patch.object(app, '_click') as click:
            with self.assertRaises(app.UnsafeUI):
                app.select_chat(object(), 'duplicado')
            click.assert_not_called()

    def test_missing_search_refuses_to_type(self):
        with patch.object(app, '_sidebar_candidates', return_value=[]), \
             patch.object(app, '_visible_controls', return_value=[]), \
             patch.object(app, '_click') as click:
            with self.assertRaises(app.UnsafeUI):
                app.select_chat(object(), 'no visible')
            click.assert_not_called()

    def test_valid_sidebar_requires_selected_confirmation(self):
        with patch.object(app, '_sidebar_candidates', return_value=[object()]), \
             patch.object(app, '_click'), \
             patch.object(app, '_verify_selected_chat') as verified:
            app.select_chat(object(), 'chat 1')
            verified.assert_called_once()

    def test_composer_ambiguous_rejected(self):
        with patch.object(app, '_visible_controls', return_value=[object(), object()]):
            with self.assertRaises(app.UnsafeUI):
                app.find_composer(object())


if __name__ == '__main__':
    unittest.main()
