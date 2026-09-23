import ast
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


class NavigationTests(unittest.TestCase):
    def test_athlete_destination_selected_before_page_work(self):
        source = (Path(__file__).resolve().parents[1] / 'views/athlete_home.py').read_text()
        tree = ast.parse(source)
        wanted = {'_photo_to_data_uri', '_render_athlete_top_navigation', 'open_athlete_page_callback'}
        pieces = []
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in wanted:
                pieces.append(ast.get_source_segment(source, node))
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ATHLETE_NAV_ITEMS' for t in node.targets):
                pieces.append(ast.get_source_segment(source, node))
        program = 'import streamlit as st\nimport base64\n' + '\n\n'.join(pieces)
        program += '''
st.session_state.setdefault('user_id', 'test-athlete')
st.session_state.setdefault('current_page', 'Athlete Home')
st.session_state.setdefault('visited', [])
st.session_state.visited.append(st.session_state.current_page)
_render_athlete_top_navigation({'name': 'Test Athlete'})
'''
        app = AppTest.from_string(program).run()
        self.assertFalse(app.exception)
        app.button(key='athlete_avatar_circle').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.visited, ['Athlete Home', 'Profile'])
        app.button(key='athlete_header_notifications').click().run()
        self.assertEqual(app.session_state.visited, ['Athlete Home', 'Profile', 'Notifications'])
