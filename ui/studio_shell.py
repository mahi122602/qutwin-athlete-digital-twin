"""Shared editorial Training Studio shell for native Streamlit pages."""
from pathlib import Path
from html import escape
import streamlit as st

PALETTES = {
 'dawn':dict(bg='#fcfaf4',panel='#fffdf8',ink='#193e38',muted='#52675e',line='#d7dfd3',soft='#edf1e7',accent='#925b37',high='#984d48',medium='#826527',low='#416b52'),
 'dusk':dict(bg='#142328',panel='#1c3034',ink='#f0f1e7',muted='#bacbc6',line='#425c60',soft='#2b4246',accent='#d8b28b',high='#e4aaa1',medium='#dec58d',low='#accfb5')}
ROUTES = [('Studio','Athlete Home'),('Add activity','Upload Garmin Data'),('Prediction & recommendation','Predictions & Coach Recommendations'),('Forecasting','Forecasting'),('Journal','Digital Twin History'),('Coach','Requests')]
def palette():
    return PALETTES.get(st.session_state.get('studio_theme_'+str(st.session_state.get('user_id')),'dawn'),PALETTES['dawn'])
def go(page):
    st.session_state.current_page=page

def apply_suite_theme():
    p=palette(); css=Path(__file__).with_name('studio_suite.css').read_text()
    variables=';'.join('--qs-'+k+':'+v for k,v in p.items())
    st.html('<style>:root{'+variables+'}'+css+'</style>')
    try:
        import plotly.io as pio
        import plotly.graph_objects as go
        pio.templates['qutwin']=go.layout.Template(layout=dict(paper_bgcolor=p['panel'],plot_bgcolor=p['panel'],font=dict(family='Arial',size=16,color=p['ink']),colorway=[p['accent'],p['low'],p['high'],p['medium']],xaxis=dict(gridcolor=p['line']),yaxis=dict(gridcolor=p['line']),margin=dict(l=40,r=25,t=55,b=45)))
        pio.templates.default='qutwin'
    except ImportError: pass

def render_shell():
    apply_suite_theme()
    with st.container(key='studio_suite_nav'):
        a,c=st.columns([7,2])
        with a: st.html('<div class="qs-brand">◇ QUTwin <span>YOUR TRAINING STUDIO</span></div>')
        with c:
            options={'Explore…':None,'What-if studio':'What-if Simulation','Visualisations':'Visualisations / Graphs','My profile':'Profile','Notifications':'Notifications','Settings':'Settings','Digital twin':'Digital Twin Dashboard'}
            choice=st.selectbox('Explore',list(options),label_visibility='collapsed',key='suite_explore')
            if options[choice]:
                go(options[choice]);del st.session_state['suite_explore'];st.rerun()
        for col,(label,page) in zip(st.columns([1,1.2,2.3,1.3,1,1]),ROUTES):
            col.button(label,key='suite_nav_'+page,on_click=go,args=(page,),use_container_width=True,type='primary' if st.session_state.current_page==page else 'secondary')

def chapter(label,description):
    st.html(f'<div class="qs-chapter"><span>{escape(label)}</span><p>{escape(description)}</p></div>')

def score_ribbon(snapshot):
    import math
    items=[]
    for label,key,desc in [('Fatigue','fatigue_score','Higher means more estimated fatigue'),('Readiness','readiness_score','An estimated index, not clearance to train')]:
        try:
            value=float(snapshot.get(key)); valid=math.isfinite(value) and 0<=value<=100
        except (ValueError,TypeError): value=0; valid=False
        display=f'{value:.1f} / 100' if valid else 'Not assessed'
        bar=f'<div class="qs-track"><i style="width:{value}%"></i></div>' if valid else ''
        missing='Outside model coverage · see assessment details' if snapshot.get('outside_training_range') else 'Add a supported set of measurements below'
        items.append(f'<article class="qs-score"><span>{label}</span><strong>{display}</strong>{bar}<small>{desc if valid else missing}</small></article>')
    risk=str(snapshot.get('injury_risk') or 'Not assessed');risk='Not assessed' if risk.lower() in ('nan','none','') else risk;cls={'high':'high','medium':'medium','low':'low'}.get(risk.lower(),'unknown')
    items.append(f'<article class="qs-score qs-{cls}"><span>Exploratory injury category</span><strong>{escape(risk)}</strong><small>Research estimate · not an injury probability</small></article>')
    st.html('<div class="qs-scores">'+''.join(items)+'</div>')

def style_chart(fig):
    """Set nested Plotly colours explicitly; old figure fonts override templates."""
    p=palette()
    font=dict(family='Arial, sans-serif',color=p['ink'],size=17)
    fig.update_layout(
        template='plotly_dark' if p is PALETTES['dusk'] else 'plotly_white',
        paper_bgcolor=p['panel'],plot_bgcolor=p['panel'],font=font,
        title_font=dict(color=p['ink'],size=22),
        colorway=[p['accent'],p['low'],p['high'],p['medium']],
        legend=dict(orientation='h',y=-.25,font=font,title_font=font),
        hoverlabel=dict(bgcolor=p['panel'],font=font,bordercolor=p['line']),
        hovermode='x unified',margin=dict(l=65,r=30,t=65,b=100))
    axis=dict(color=p['ink'],tickfont=font,title_font=font,
              gridcolor=p['line'],linecolor=p['line'],zerolinecolor=p['line'],automargin=True)
    fig.update_xaxes(**axis);fig.update_yaxes(**axis)
    for annotation in fig.layout.annotations:
        annotation.font.update(color=p['ink'],size=17)
    fig.update_layout(polar=dict(bgcolor=p['panel'],
        angularaxis=dict(color=p['ink'],tickfont=font,gridcolor=p['line']),
        radialaxis=dict(color=p['ink'],tickfont=font,gridcolor=p['line'])))
    return fig
