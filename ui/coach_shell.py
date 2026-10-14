"""Client-approved coach studio: shared scene, navigation and accessible motion."""
from pathlib import Path
from html import escape
import base64
import re
import streamlit as st
from ui.studio_shell import apply_suite_theme

INSIGHTS={'Priorities':'Intelligence','Athlete overview':'Twin Summary','Visualisation':'Visualisation','Forecasting':'Forecasting','History':'History','Activity trail':'Timeline','Model evaluation':'Model Evaluation'}
PAGES=['Dashboard','Athletes','Teams',*INSIGHTS.values(),'Reviews','Connections','Notifications','Profile','Athlete Detail','Team Detail']

def go(page,athlete=None,team=None,upload=None):
    if page not in PAGES:return
    if st.session_state.get('coach_page')!=page:
        st.session_state.coach_transition=st.session_state.get('coach_transition',0)+1
    st.session_state.coach_page=page
    if athlete is not None:
        st.session_state.coach_athlete=str(athlete)
        # Reset page-specific selectors, so row links and notification links agree.
        for k in list(st.session_state):
            if str(k).startswith('cs_select_'):del st.session_state[k]
    if team is not None:st.session_state.coach_team=int(team)
    if upload is not None:st.session_state.coach_upload=int(upload)

def toggle_theme():
    key='studio_theme_'+str(st.session_state.user_id)
    st.session_state[key]='dusk' if st.session_state.get(key,'dawn')=='dawn' else 'dawn'

def sign_out():
    st.session_state.clear()

@st.cache_data(show_spinner=False)
def scene_uri(theme):
    p=Path(__file__).with_name('coach_assets')/('coach-'+theme+'.webp')
    return 'data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode('ascii') if p.exists() else ''

def shell():
    apply_suite_theme()
    theme=st.session_state.get('studio_theme_'+str(st.session_state.user_id),'dawn')
    css=Path(__file__).with_name('coach_suite.css').read_text()
    if theme=='dawn':
        css+='\n'+Path(__file__).with_name('coach_dawn.css').read_text()
    variables=('--cs-surface:#fffdf7f5;--cs-nav:#fffaf0ee;--cs-input:#fffdf8;--cs-ink:#173b32;--cs-muted:#51665e;--cs-line:#d6ddd3;--cs-accent:#99582e;--cs-high:#ae342f;--cs-medium:#866016;--cs-low:#23764e;' if theme=='dawn' else '--cs-surface:#102b24f5;--cs-nav:#102b24ee;--cs-input:#203c33;--cs-ink:#f7f3e8;--cs-muted:#c3d0c5;--cs-line:#4b6356;--cs-accent:#efb47f;--cs-high:#ffaaa1;--cs-medium:#f4d18b;--cs-low:#9fe0b7;')
    scene_class=' home' if st.session_state.get('coach_page','Dashboard')=='Dashboard' else ''
    st.html('<style>:root{'+variables+'}'+css+'</style><div aria-hidden="true" class="cs-scene '+theme+scene_class+'"><div class="cs-scene-dawn" style="background-image:url('+scene_uri('dawn')+')"></div><div class="cs-scene-dusk" style="background-image:url('+scene_uri('dusk')+')"></div></div>')
    page=st.session_state.get('coach_page','Dashboard')
    with st.container(key='coach_studio_nav'):
        cols=st.columns([1.65,1.1,1,.85,1.1,1,1.35,.95,.45,.45],vertical_alignment='center')
        brand=cols[0];nav=cols[1:7];theme_col,bell,avatar=cols[7:]
        brand.markdown('<div class="cs-brand">QUTwin</div>',unsafe_allow_html=True)
        theme_col.button(('☀ Dawn' if theme=='dawn' else '☾ Dusk'),help='Switch the theme for every coach page',key='coach_theme',on_click=toggle_theme,use_container_width=True)
        bell.button(' ',icon=':material/notifications:',help='Notifications',key='csbell',on_click=go,args=('Notifications',),use_container_width=True)
        initials=''.join(x[:1] for x in st.session_state.get('coach_display_name','Coach').split())[:2].upper()
        avatar.button(initials,help='My profile',key='csprofile',on_click=go,args=('Profile',),use_container_width=True)
        for col,label in zip(nav[:3],['Dashboard','Athletes','Teams']):
            col.button(label,key='csnav'+label,on_click=go,args=(label,),type='primary' if page==label else 'secondary',use_container_width=True)
        with nav[3].popover('Insights',use_container_width=True):
            for label,dest in INSIGHTS.items():st.button(label,key='ins'+dest,on_click=go,args=(dest,),use_container_width=True)
        nav[4].button('Reviews',key='csnavReviews',on_click=go,args=('Reviews',),type='primary' if page=='Reviews' else 'secondary',use_container_width=True)
        nav[5].button('Connections',key='csnavConnections',on_click=go,args=('Connections',),type='primary' if page=='Connections' else 'secondary',use_container_width=True)

def heading(title,subtitle=''):
    st.html(f'<div class="cs-heading"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>')

def badge(label):
    kind={'High':'high','Medium':'medium','Low':'low'}.get(str(label),'unknown')
    return f'<span class="cs-badge {kind}"><i></i>{escape(str(label))}</span>'

def attention_card(label,count,description):
    kind={'High':'high','Medium':'medium','Low':'low'}.get(label,'unknown')
    st.html(f'<article class="cs-attention {kind}"><span>{badge(label)}</span><strong>{int(count)}</strong><p>{escape(description)}</p></article>')
