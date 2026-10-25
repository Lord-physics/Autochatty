import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from export_import import import_export, InvalidExport, UNKNOWN_PROJECT

class ExportTests(unittest.TestCase):
    def make(self, contents):
        tmp = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        tmp.close()
        with ZipFile(tmp.name,'w') as z:
            for name, data in contents.items():
                z.writestr(name, json.dumps(data))
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_explicit_titles_only_and_verified_project(self):
        name=self.make({'conversations.json':[
             {'title':'Real', 'id':'abc1', 'project_id':'p1'},
             {'title':'Otro real','id':'abc2'},
             {'title':'','id':'abc3'}, {'title':'Sin ID'},
             {'title':'Real','id':'abc1'}],
             'projects.json':[{'id':'p1','name':'Trabajo real'}]})
        r=import_export(name)
        self.assertEqual([c.title for c in r], ['Real','Otro real'])
        self.assertEqual(r[0].project, 'Trabajo real')
        self.assertEqual(r[1].project, UNKNOWN_PROJECT)
    def test_no_inferred_project(self):
        name=self.make({'conversations.json':[{'title':'Proyecto Marte','id':'id123','project_id':'unknown'}]})
        self.assertEqual(import_export(name)[0].project, UNKNOWN_PROJECT)
    def test_duplicate_titles_flagged(self):
        name=self.make({'conversations.json': [{'title':'Mismo', 'id':'one'}, {'title':'Mismo', 'id':'two'}]})
        self.assertEqual([x.duplicates for x in import_export(name)],[2,2])
    def test_reject_unknown_zip(self):
        name=self.make({'random.json':[]})
        with self.assertRaises(InvalidExport): import_export(name)
    def test_subfolder_json(self):
        name=self.make({'ChatGPT Export/conversations.json':[{'title':'A chat','id':'aaa'}]})
        self.assertEqual(import_export(name)[0].title,'A chat')

if __name__=='__main__': unittest.main()
