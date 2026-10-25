import unittest
from datetime import datetime, timezone
from state_machine import apply_result, prepare_attempt, mark_submitted, reset_attempt


class StateMachineTests(unittest.TestCase):
    def setUp(self):
        self.chat = {'status': 'pendiente', 'last_result': '', 'cooldown_until': ''}
        self.now = datetime(2026, 10, 25, 2, 30, tzinfo=timezone.utc)

    def test_done_clears_token(self):
        prepare_attempt(self.chat, True, lambda: 'f'*24)
        mark_submitted(self.chat)
        apply_result(self.chat, 'done', 'Sí', self.now)
        self.assertEqual(self.chat['status'], 'terminado')
        self.assertEqual(self.chat['pending_token'], '')

    def test_no_marker_is_review_and_keeps_token(self):
        prepare_attempt(self.chat, True, lambda: 'f'*24)
        mark_submitted(self.chat)
        apply_result(self.chat, 'review', 'No está claro', self.now)
        self.assertEqual(self.chat['status'], 'revision')
        self.assertEqual(self.chat['pending_token'], 'f'*24)

    def test_timeout_is_not_finished(self):
        prepare_attempt(self.chat, True, lambda: 'f'*24)
        mark_submitted(self.chat)
        apply_result(self.chat, 'timeout', 'Aún ocupado', self.now)
        self.assertEqual(self.chat['status'], 'en_curso')
        self.assertEqual(self.chat['pending_token'], 'f'*24)
        self.assertTrue(self.chat['cooldown_until'])

    def test_blocked_prevents_auto_retry(self):
        prepare_attempt(self.chat, True, lambda: 'f'*24)
        apply_result(self.chat, 'blocked', 'Necesita permiso', self.now)
        self.assertEqual(self.chat['status'], 'bloqueado')

    def test_resume_reuses_token(self):
        prepare_attempt(self.chat, True, lambda: 'f'*24)
        prepare_attempt(self.chat, True, lambda: 'a'*24)
        self.assertEqual(self.chat['pending_token'], 'f'*24)

    def test_manual_reset(self):
        prepare_attempt(self.chat, True, lambda: 'f'*24)
        reset_attempt(self.chat, 'pendiente')
        self.assertEqual(self.chat['pending_token'], '')
        self.assertEqual(self.chat['status'], 'pendiente')

if __name__ == '__main__':
    unittest.main()
