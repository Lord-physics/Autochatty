import unittest
from test_chat_discovery import Control, Window, W
from project_discovery import scan_visible_projects


class ProjectDiscoveryTests(unittest.TestCase):
    def test_project_button_under_project_heading(self):
        w = Window([])
        heading = Control('Proyectos', 'Text', (18,80,210,110), w)
        project = Control('CanSat', 'Button', (30,136,270,166), w)
        w.children = [heading,project]
        self.assertEqual([x.name for x in scan_visible_projects(w)], ['CanSat'])

    def test_no_invented_project_without_heading(self):
        w = Window([])
        project = Control('CanSat', 'Button', (30,136,270,166), w)
        w.children = [project]
        self.assertEqual(scan_visible_projects(w), [])

    def test_project_section_does_not_include_recents(self):
        w = Window([])
        projects = Control('Proyectos', 'Text', (18,80,210,110), w)
        project = Control('Proyecto real', 'Hyperlink', (30,136,270,166), w)
        recents = Control('Recientes', 'Text', (18,190,210,220), w)
        chat = Control('Chat cualquiera', 'Hyperlink', (30,250,270,280), w)
        w.children = [projects,project,recents,chat]
        self.assertEqual([x.name for x in scan_visible_projects(w)], ['Proyecto real'])

    def test_project_heading_is_not_project(self):
        w = Window([])
        projects = Control('Proyectos', 'Text', (18,80,210,110), w)
        w.children = [projects]
        self.assertEqual(scan_visible_projects(w), [])

if __name__ == '__main__':
    unittest.main()
