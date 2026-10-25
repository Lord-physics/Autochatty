import unittest
from unittest.mock import patch

import runner


class FakeClock:
    def __init__(self):
        self.t = 0
    def now(self):
        return self.t
    def advance(self, s):
        self.t += s


class RunnerTests(unittest.TestCase):
    chat = {'name':'Mision','app_title':'Mision','id':'e501b3fc-1abe-4c28-82a8-3e703b4c5ceb',
            'instruction':'Continua','pending_token':'1'*24, 'expected_files':''}

    def test_idle_without_local_proof_is_review(self):
        clock = FakeClock()
        with patch.object(runner.time, 'monotonic', clock.now), \
             patch.object(runner.time, 'sleep', clock.advance), \
             patch.object(runner.signals, 'check', lambda _: None), \
             patch.object(runner.app_adapter, 'interactive_desktop', lambda: True), \
             patch.object(runner.app_adapter, 'generating', lambda _: False):
            state, _ = runner._observe(object(), self.chat, lambda _: None)
        self.assertEqual(state, 'review')
        self.assertGreaterEqual(clock.t, 100)

    def test_local_done_is_enough_for_runner(self):
        with patch.object(runner.signals, 'check', lambda _: ('done', 'Validado')):
            self.assertEqual(runner._observe(object(), self.chat, lambda _: None)[0], 'done')

    def test_overtime_requires_no_new_send(self):
        clock = FakeClock()
        with patch.object(runner.time, 'monotonic', clock.now), \
             patch.object(runner.time, 'sleep', clock.advance), \
             patch.object(runner, 'MAX_WAIT_SECONDS', 18), \
             patch.object(runner.signals, 'check', lambda _: None), \
             patch.object(runner.app_adapter, 'interactive_desktop', lambda: True), \
             patch.object(runner.app_adapter, 'generating', lambda _: True):
            state, _ = runner._observe(object(), self.chat, lambda _: None)
        self.assertEqual(state, 'timeout')

    def test_resource_guard_no_app_opened(self):
        with patch.object(runner.os, 'name', 'nt'), \
             patch.object(runner, 'free_ram_percent', lambda: 2), \
             patch.object(runner.app_adapter, 'ensure_app_window') as opened:
            state, _ = runner.run(self.chat, False, 20)
        self.assertEqual(state, 'memory')
        opened.assert_not_called()

    def test_existing_sent_attempt_cannot_be_resent(self):
        with patch.object(runner.os, 'name', 'nt'), \
             patch.object(runner, 'free_ram_percent', lambda: 95), \
             patch.object(runner, 'cpu_percent', lambda: 5), \
             patch.object(runner.signals, 'check', lambda _: None), \
             patch.object(runner.app_adapter, 'submit') as submitted:
            state, _ = runner.run(self.chat, True, 10, fresh_attempt=False)
        self.assertEqual(state, 'review')
        submitted.assert_not_called()

    def test_no_windows(self):
        with patch.object(runner.os, 'name', 'posix'):
            self.assertEqual(runner.run(self.chat, False, 10)[0], 'error')


if __name__ == '__main__':
    unittest.main()
