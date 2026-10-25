import unittest
from unittest.mock import Mock
from chat_discovery import is_candidate, scan_window
W=(0,0,1200,800)
class UIARect:
    def __init__(self, r): self.left,self.top,self.right,self.bottom=r
class Control:
    def __init__(self,name,role,rect,parent=None,visible=True):
        self._name=name; self._rect=rect; self._parent=parent; self._visible=visible
        self.element_info=Mock(control_type=role)
    def window_text(self): return self._name
    def rectangle(self): return UIARect(self._rect)
    def is_visible(self): return self._visible
    def parent(self): return self._parent
class Window(Control):
    def __init__(self,children):
        super().__init__('ChatGPT','Window',W)
        self.children=children
    def descendants(self): return self.children
class DiscoveryTests(unittest.TestCase):
    def test_no_unverified_text_or_sidebar_button(self):
        self.assertFalse(is_candidate('Nuevo chat','Button',(40,180,200,204),W))
        self.assertFalse(is_candidate('Respuesta del asistente','Text',(40,180,300,204),W))
    def test_only_explicit_chat_list(self):
        win=Window([])
        parent=Control('Chats','List',(5,90,440,700),parent=win)
        good=Control('Título real','ListItem',(40,180,300,205),parent)
        bad=Control('Nombre de proyecto','ListItem',(40,220,300,245),Control('Proyectos','Group',(5,80,440,690),win))
        nav=Control('Buscar chats','Button',(40,260,300,285),parent)
        win.children=[good,bad,nav]
        found=scan_window(win)
        self.assertEqual([x.title for x in found],['Título real'])
    def test_nested_duplicates_collapse(self):
        win=Window([])
        parent=Control('Chats','List',(5,90,440,700),parent=win)
        win.children=[Control('Real','ListItem',(40,180,300,205),parent), Control('Real','ListItem',(40,181,300,206),parent)]
        self.assertEqual(scan_window(win)[0].duplicates,1)
    def test_two_same_titles_flag(self):
        win=Window([])
        parent=Control('Chats','List',(5,90,440,700),parent=win)
        win.children=[Control('Real','ListItem',(40,180,300,205),parent), Control('Real','ListItem',(40,220,300,245),parent)]
        self.assertEqual(scan_window(win)[0].duplicates,2)
if __name__=='__main__': unittest.main()

class ScanMoreTests(unittest.TestCase):
    def test_short_real_title(self):
        self.assertTrue(is_candidate('X','ListItem',(40,180,300,205),W))
    def test_nested_project_uses_actual_heading(self):
        from chat_discovery import scan_window_with_projects
        win=Window([])
        projects=Control('Proyectos','Tree',(1,40,420,750),parent=win)
        proj=Control('Proyecto A','TreeItem',(20,100,400,124),parent=projects)
        item=Control('Chat exacto','TreeItem',(45,160,340,185),parent=proj)
        win.children=[projects,proj,item]
        result=scan_window_with_projects(win)
        self.assertEqual([(x.title,x.project) for x in result],[('Chat exacto','Proyecto A')])
    def test_sidebar_project_label_not_mistaken_for_chat(self):
        win=Window([])
        projects=Control('Proyectos','Tree',(1,40,420,750),parent=win)
        proj=Control('Proyecto A','TreeItem',(20,100,400,124),parent=projects)
        win.children=[projects,proj]
        self.assertEqual(scan_window(win),[])


class ChromiumSidebarTests(unittest.TestCase):
    def test_link_below_text_heading_is_verified(self):
        win=Window([])
        heading=Control('Chats','Text',(25,90,180,115),win)
        item=Control('Cálculo de ondas','Hyperlink',(30,145,320,173),win)
        win.children=[heading,item]
        from chat_discovery import scan_window_with_projects,UNKNOWN_PROJECT
        self.assertEqual([(c.title,c.project) for c in scan_window_with_projects(win)],
                         [('Cálculo de ondas',UNKNOWN_PROJECT)])

    def test_button_below_chat_heading_but_not_navigation_controls(self):
        win=Window([])
        heading=Control('Chats','Header',(25,90,180,114),win)
        actual=Control('Trabajo de programación','Button',(40,151,290,180),win)
        navigation=Control('New chat','Button',(40,185,290,210),win)
        win.children=[heading,actual,navigation]
        self.assertEqual([c.title for c in scan_window(win)],['Trabajo de programación'])

    def test_text_child_requires_clickable_parent(self):
        win=Window([])
        heading=Control('Chats','Text',(25,90,180,114),win)
        clickable=Control('','Hyperlink',(30,130,390,170),win)
        title=Control('Proyecto satélite','Text',(45,140,280,160),clickable)
        unrelated=Control('No es un chat','Text',(45,200,280,220),win)
        win.children=[heading,clickable,title,unrelated]
        self.assertEqual([c.title for c in scan_window(win)],['Proyecto satélite'])

    def test_following_projects_section_stops_chat_scan(self):
        win=Window([])
        heading=Control('Chats','Text',(25,90,180,114),win)
        title=Control('Chat de verdad','Hyperlink',(45,160,280,188),win)
        projects=Control('Proyectos','Text',(25,200,180,230),win)
        project_button=Control('Proyecto documentación','Button',(45,250,280,280),win)
        win.children=[heading,title,projects,project_button]
        self.assertEqual([c.title for c in scan_window(win)],['Chat de verdad'])

    def test_no_heading_no_nav_list_no_chats(self):
        win=Window([Control('Nombre ambiguo','Hyperlink',(45,160,280,190),None)])
        self.assertEqual(scan_window(win),[])

    def test_repeated_real_chat_titles_rejected_as_ambiguous(self):
        win=Window([])
        heading=Control('Chats','Text',(25,90,180,114),win)
        one=Control('Igual','Hyperlink',(45,160,280,187),win)
        two=Control('Igual','Hyperlink',(45,205,280,233),win)
        win.children=[heading,one,two]
        self.assertEqual(scan_window(win)[0].duplicates,2)
