import unittest
from test_chat_discovery import Control, Window
from uia_diagnostic import describe_window


class DiagnosticTests(unittest.TestCase):
    def test_private_labels_redacted(self):
        w = Window([])
        w.children = [Control('Recientes','Text',(5,80,100,100),w),
                      Control('Chat secreto personal','Hyperlink',(10,125,250,155),w),
                      Control('Proyecto confidencial','Button',(10,165,250,195),w)]
        report = describe_window(w)
        self.assertIn('recientes', [x['label_class'] for x in report['sidebar_controls']])
        rendered = str(report)
        self.assertNotIn('Chat secreto personal', rendered)
        self.assertNotIn('Proyecto confidencial', rendered)
        self.assertTrue(report['private_names_excluded'])

if __name__ == '__main__':
    unittest.main()
