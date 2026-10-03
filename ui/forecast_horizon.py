"""Athlete-facing forecast horizon with day focus and honest evidence status."""
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui.studio_shell import style_chart,palette
from forecasting.validated import TARGETS


def render_forecast_horizon(table,bundle):
    p=palette()
    st.html('''<style>
    .forecast-heading{border-left:3px solid var(--qs-accent);padding:12px 24px;margin:18px 0 26px}
    .forecast-heading h2{font:400 34px Georgia,serif;margin:4px 0 10px}
    .forecast-heading p{max-width:800px}
    @media(prefers-reduced-motion:no-preference){.forecast-heading{animation:horizon-in .55s ease-out}@keyframes horizon-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}}
    </style><section class="forecast-heading"><h2>Your next seven days</h2><p>Explore one measure, focus on a day, and see how much evidence supports the projection.</p></section>''')
    labels=[v for v in TARGETS.values() if v in table]
    if not labels:st.info('No usable index is available for this forecast.');return
    metric=st.radio('What would you like to explore?',labels,horizontal=True,key='horizon_target')
    frame=table.reset_index(drop=True)
    day=st.select_slider('Move through your forecast',options=list(range(len(frame))),format_func=lambda i:pd.Timestamp(frame.iloc[i]['Date']).strftime('%a %d %b'),key='horizon_focus')
    row=frame.iloc[day];low=row.get(metric+' lower');high=row.get(metric+' upper')
    first,second,third=st.columns(3)
    first.metric(metric.replace(' forecast',''),f"{row[metric]:.1f} / 100")
    second.metric('Empirical range',f'{low:.1f}–{high:.1f}' if pd.notna(low) and pd.notna(high) else 'Not established')
    third.metric('Recorded days',bundle.data_points)
    fig=go.Figure()
    if frame[metric+' lower'].notna().any():
        fig.add_trace(go.Scatter(x=frame.Date,y=frame[metric+' upper'],line=dict(width=0),showlegend=False,hoverinfo='skip',connectgaps=False))
        fig.add_trace(go.Scatter(x=frame.Date,y=frame[metric+' lower'],fill='tonexty',fillcolor='rgba(150,170,150,0.22)',line=dict(width=0),name='Empirical error range',connectgaps=False))
    fig.add_trace(go.Scatter(x=frame.Date,y=frame[metric],mode='lines+markers',name=metric,line=dict(width=4,color=p['accent']),marker=dict(size=9)))
    fig.add_trace(go.Scatter(x=[row.Date],y=[row[metric]],mode='markers',name='Selected day',marker=dict(size=18,color=p['ink'],symbol='circle-open',line=dict(width=3))))
    fig.update_layout(height=410,yaxis_title='Index / 100');fig.update_yaxes(range=[0,100])
    st.plotly_chart(style_chart(fig),theme=None,use_container_width=True)
    st.caption('Ranges use the 90th percentile of earlier forecast errors, separately for each day ahead. They are not a 90% accuracy promise. When evidence is insufficient, no range is drawn. Forecasts of research scores do not establish changes in physical health.')
    evaluation=bundle.evaluation
    if not evaluation.empty:
        e=evaluation[evaluation.Target.eq(metric)]
        tested=e.dropna(subset=['MAE (points)'])
        if not tested.empty:
            mae=tested['MAE (points)'].mean();baseline=tested['Baseline MAE (points)'].mean()
            st.write(f'**How it performed on later held-out history:** average error {mae:.1f} points; repeating the last value had an average error of {baseline:.1f} points. These summarise the tested 1–7 day horizons.')
            if mae>=baseline:st.info('The selected method did not improve on the simple baseline in the later test period. Treat this forecast cautiously.')
        else:st.info('Not enough later observations to measure forecast error yet.')
    else:st.info('Starting baseline: more dated history is needed before methods and error ranges can be assessed.')
    st.write('**Injury probability: not available.** The current research categories are not verified future injury outcomes. This page does not convert them into percentages or invent an injury forecast.')
    visual,daily=st.tabs(['How to use this','Daily values'])
    with visual:
        st.write('Use the projection as a discussion aid with your coach. Higher fatigue means more estimated fatigue; readiness is an index, not clearance to train. Missing scores remain unavailable.')
        coach=frame.iloc[0].get('Coach recommendation')
        if coach:st.write('**Coach recommendation**');st.write(coach)
    with daily:
        columns=['Date',metric,metric+' lower',metric+' upper']
        st.dataframe(frame[columns].rename(columns={metric+' lower':'Range lower',metric+' upper':'Range upper'}),hide_index=True,use_container_width=True)
        st.download_button('Download these daily values',frame[columns].to_csv(index=False).encode(),'qutwin_forecast.csv','text/csv')
    with st.expander('How this forecast was checked'):
        st.write('Earlier dates select the method; a separate middle period sets error ranges; the latest period tests the frozen choice. Only observations before each forecast origin are used. Missing dates are not interpolated. Repeated test windows overlap, so their errors are not independent samples. These are internal checks, not external clinical validation.')
        st.dataframe(bundle.model_weights,hide_index=True,use_container_width=True)
        if not evaluation.empty:st.dataframe(evaluation,hide_index=True,use_container_width=True)
