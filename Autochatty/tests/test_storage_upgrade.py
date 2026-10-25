import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import storage


class StorageUpgradeTests(unittest.TestCase):
    def test_v3_does_not_keep_auto_send_permission(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'controller.json'
            f.write_text(json.dumps({'version':3, 'auto_send':True,'chats':[{'id':'abc','name':'Proyecto','status':'pendiente'}]}))
            with patch.object(storage,'APP_DIR',Path(folder)),patch.object(storage,'CONFIG_FILE',f):
                cfg=storage.load()
            self.assertFalse(cfg['auto_send'])
            self.assertEqual(cfg['version'],8)

    def test_v2_does_not_keep_auto_send_permission(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'controller.json'
            f.write_text(json.dumps({'version':2, 'auto_send':True, 'chats':[
                {'name':'Chat anterior','id':'e501b3fc-1abe-4c28-82a8-3e703b4c5ceb',
                 'status':'en_curso','pending_token':'1'*24,'attempt_state':'submitted'}]}))
            with patch.object(storage,'APP_DIR',Path(folder)), patch.object(storage,'CONFIG_FILE',f):
                cfg=storage.load()
                self.assertFalse(cfg['auto_send'])
                self.assertEqual(cfg['chats'][0]['app_title'], 'Chat anterior')
                self.assertEqual(cfg['chats'][0]['status'], 'revision')
                self.assertEqual(cfg['chats'][0]['pending_token'], '')
                self.assertEqual(cfg['version'],8)


if __name__ == '__main__':
    unittest.main()
