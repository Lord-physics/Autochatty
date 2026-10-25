import unittest
from datetime import datetime, timedelta, timezone

from scheduler import candidate, due, parse_clock, parse_times, valid_chat_url, window_active


class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.tz = timezone(timedelta(hours=2))

    def test_midnight(self):
        self.assertTrue(window_active(datetime(2026, 10, 25, 2, 30), '23:00', '05:00'))
        self.assertFalse(window_active(datetime(2026, 10, 25, 12, 30), '23:00', '05:00'))

    def test_exact(self):
        cfg = {'enabled': True, 'schedule_mode': 'horas', 'exact_times': '02:00, 06:00', 'last_run_key': ''}
        now = datetime(2026, 10, 25, 2, 4, tzinfo=self.tz)
        yes, key = due(now, cfg)
        self.assertTrue(yes)
        cfg['last_run_key'] = key
        self.assertFalse(due(now, cfg)[0])

    def test_selected_preferred(self):
        now = datetime.now().astimezone()
        chats = [
            {'name': 'A', 'status': 'pendiente', 'selected': False},
            {'name': 'B', 'status': 'en_curso', 'selected': True},
        ]
        self.assertEqual(candidate(chats, now)['name'], 'B')
        chats[1]['status'] = 'terminado'
        self.assertEqual(candidate(chats, now)['name'], 'A')

    def test_url(self):
        self.assertTrue(valid_chat_url('https://chatgpt.com/c/abc-def'))
        self.assertFalse(valid_chat_url('https://malicious.example/c/abc'))
        self.assertFalse(valid_chat_url('http://chatgpt.com/c/abc'))

    def test_parse(self):
        self.assertEqual(len(parse_times('03:00, 03:00, 05:30')), 2)
        with self.assertRaises(ValueError):
            parse_clock('25:00')


if __name__ == '__main__':
    unittest.main()
