import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import signals


class SignalTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.patch = patch.object(signals, 'SIGNAL_DIR', Path(self.dir.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.chat = {'id':'e501b3fc-1abe-4c28-82a8-3e703b4c5ceb',
                     'pending_token':'1'*24, 'expected_files':''}

    def test_done_requires_correct_id_and_token(self):
        signals.write_signal(self.chat['id'], self.chat['pending_token'], 'TERMINADO', 'Fin')
        self.assertEqual(signals.check(self.chat), ('done', 'Fin'))
        self.assertIsNone(signals.check({**self.chat,'pending_token':'2'*24}))

    def test_unverified_local_file_blocks_done(self):
        self.chat['expected_files'] = str(Path(self.dir.name) / 'sin_salida.txt')
        signals.write_signal(self.chat['id'], self.chat['pending_token'], 'TERMINADO')
        self.assertEqual(signals.check(self.chat)[0], 'review')

    def test_pending_and_blocked(self):
        for estado, resultado in [('PENDIENTE','pending'), ('BLOQUEADO','blocked')]:
            signals.write_signal(self.chat['id'], self.chat['pending_token'], estado)
            self.assertEqual(signals.check(self.chat)[0], resultado)

    def test_malformed_is_not_done(self):
        signals.SIGNAL_DIR.mkdir(exist_ok=True, parents=True)
        signals.signal_path(self.chat).write_text('{invalid', encoding='utf-8')
        self.assertEqual(signals.check(self.chat)[0], 'review')

    def test_wrong_chat_path_blocked(self):
        with self.assertRaises(ValueError):
            signals.signal_path({'id':'../../contraseña', 'pending_token':'1'*24})


if __name__ == '__main__':
    unittest.main()
