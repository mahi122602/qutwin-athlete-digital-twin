"""Client-approved coach studio: shared scene, navigation and accessible motion."""
from pathlib import Path
from html import escape
import base64
import re
import streamlit as st
from ui.studio_shell import apply_suite_theme

# Keep these layout rules last, including when an older coach_suite.css remains.
# An explicit stacking context is essential: the fixed scene otherwise paints
# over non-positioned panel backgrounds when their entrance animation finishes.
COACH_LAYOUT_BUILD = 'coach-photo-gap-v2-20261018'
COACH_LAYOUT_CSS = r'''
:root{--cs-nav-height:76px;--cs-content-gap:24px}
.stApp:has(.st-key-coach_studio_nav),
[data-testid="stAppViewContainer"]:has(.st-key-coach_studio_nav),
[data-testid="stMain"]:has(.st-key-coach_studio_nav),
[data-testid="stMainBlockContainer"]:has(.st-key-coach_studio_nav),
[data-testid="stVerticalBlock"]:has(.st-key-coach_studio_nav),
[data-testid="stLayoutWrapper"]:has(.st-key-coach_studio_nav){
  transform:none!important;filter:none!important;backdrop-filter:none!important;
  perspective:none!important;contain:none!important;will-change:auto!important;
  animation:none!important;opacity:1!important;
}
[data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"]:has(.st-key-coach_studio_nav){
  padding:calc(var(--cs-nav-height) + var(--cs-content-gap)) 2.2vw 4rem!important;max-width:1920px!important;
  position:relative;z-index:1;
}
[data-testid="stMainBlockContainer"]:has(.st-key-coach_studio_nav)>[data-testid="stVerticalBlock"]{gap:0!important}
.st-key-coach_studio_nav{
  position:fixed!important;inset:0 0 auto 0!important;width:100%!important;
  max-width:none!important;height:var(--cs-nav-height)!important;
  min-height:var(--cs-nav-height)!important;box-sizing:border-box;z-index:1000!important;
  margin:0!important;border-radius:0!important;padding:10px 2.2vw!important;
  gap:0!important;justify-content:center;background:var(--cs-nav)!important;
  border-bottom:1px solid var(--cs-line)!important;backdrop-filter:blur(14px);
}
/* The scene begins below the bar. A height-fitted foreground keeps the entire
   coach visible without stretching; the cover layer fills the wider canvas. */
.cs-scene:not(.home){
  position:fixed!important;
  inset:var(--cs-nav-height) 0 0 0!important;
  z-index:0!important;pointer-events:none!important;
}
.cs-scene:not(.home)>div{
  background-size:cover!important;background-position:left top!important;
  background-repeat:no-repeat!important;
}
.cs-scene:not(.home)>div::after{
  content:"";position:absolute;inset:0 auto 0 0;pointer-events:none;
  width:calc((100vh - var(--cs-nav-height,76px)) * 1.5);max-width:100%;
  background-image:inherit;background-size:auto 100%;
  background-position:left top;background-repeat:no-repeat;
  -webkit-mask-image:linear-gradient(to right,#000 70%,transparent 100%);
  mask-image:linear-gradient(to right,#000 70%,transparent 100%);
}
[class*="st-key-cs_page_"]{
  position:relative!important;z-index:2!important;isolation:isolate;
  background:var(--cs-surface)!important;color:var(--cs-ink)!important;
  border:1px solid var(--cs-line)!important;border-radius:18px!important;
  box-shadow:0 18px 60px #041a1933!important;opacity:1!important;
  backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
}
[class*="st-key-cs_page_"] .cs-heading{padding-bottom:12px;border-bottom:1px solid var(--cs-line);margin-bottom:18px}
[class*="st-key-cs_page_"] [class*="st-key-cs_row_"]{
  background:var(--cs-input)!important;border:1px solid var(--cs-line)!important;
  border-radius:12px!important;padding:14px 16px!important;margin-bottom:8px;
}
[class*="st-key-cs_page_"] .cs-table-head{
  color:var(--cs-muted)!important;font-weight:700;
}
/* The home scene already contains its own cards and readable hero panel. */
[class*="st-key-cs_page_Dashboard_"]{
  background:transparent!important;border:0!important;border-radius:0!important;
  box-shadow:none!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important;
}
@media(max-width:1000px){
  :root{--cs-nav-height:84px}
  .st-key-coach_studio_nav{padding:8px 12px!important;overflow-x:auto!important;overflow-y:hidden!important;overscroll-behavior-x:contain}
  .st-key-coach_studio_nav [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;min-width:1000px}
  .st-key-coach_studio_nav [data-testid="stColumn"]{min-width:0!important}
  .st-key-coach_studio_nav .cs-brand{font-size:24px}
  .st-key-coach_studio_nav button p{font-size:12px!important}
}
@media(max-width:700px){
  :root{--cs-content-gap:16px}
  [data-testid="stAppViewContainer"] [data-testid="stMainBlockContainer"]:has(.st-key-coach_studio_nav){padding:calc(var(--cs-nav-height) + var(--cs-content-gap)) 12px 24px!important}
  [class*="st-key-cs_page_"]{margin-top:0!important}
}
'''

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
    css+='\n'+COACH_LAYOUT_CSS
    variables=('--cs-surface:#fffdf7f5;--cs-nav:#fffaf0ee;--cs-input:#fffdf8;--cs-ink:#173b32;--cs-muted:#51665e;--cs-line:#d6ddd3;--cs-accent:#99582e;--cs-high:#ae342f;--cs-medium:#866016;--cs-low:#23764e;' if theme=='dawn' else '--cs-surface:#102b24f5;--cs-nav:#102b24ee;--cs-input:#203c33;--cs-ink:#f7f3e8;--cs-muted:#c3d0c5;--cs-line:#4b6356;--cs-accent:#efb47f;--cs-high:#ffaaa1;--cs-medium:#f4d18b;--cs-low:#9fe0b7;')
    scene_class=' home' if st.session_state.get('coach_page','Dashboard')=='Dashboard' else ''
    st.html('<style>:root{'+variables+'}'+css+'</style><div aria-hidden="true" data-coach-ui-build="'+COACH_LAYOUT_BUILD+'" class="cs-scene '+theme+scene_class+'"><div class="cs-scene-dawn" style="background-image:url('+scene_uri('dawn')+')"></div><div class="cs-scene-dusk" style="background-image:url('+scene_uri('dusk')+')"></div></div>')
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
