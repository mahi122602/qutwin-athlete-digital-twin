"""Parallel session plans; hypothetical changes never overwrite athlete records."""
import streamlit as st
import plotly.graph_objects as go
from database.workflow_repository import list_uploads
from ui.studio_shell import chapter,style_chart,palette
from ui.first_upload_forecast import finite_value


def scenario_values(duration,load,change):
    factor=1+change/100
    return {'duration':duration*factor if duration is not None else None,
            'load':load*factor if load is not None else None}


def athlete_simulation():
    st.title('What-if · Parallel paths')
    chapter('ONE START / TWO POSSIBILITIES','Explore two possible sessions side by side. Move the controls and watch their paths change. Nothing here changes your saved activity.')
    uploads=list_uploads(str(st.session_state.user_id))
    snap={}
    if uploads:
        options={str(u['id']):u for u in uploads}
        selected=st.selectbox('Start from an activity',list(options),format_func=lambda key:options[key]['filename'],key='scenario_upload')
        snap=options[selected].get('snapshot') or {}
    else:st.info('You can explore a hypothetical session now. Add an activity later to use your own baseline.')
    duration=finite_value(snap.get('duration_minutes'));load=finite_value(snap.get('training_load'))
    if duration is None:
        duration=st.number_input('Hypothetical starting duration (minutes)',min_value=1.0,max_value=1440.0,value=None,placeholder='For example, 30',key='scenario_duration')
        st.caption('Optional scenario input only. This will not be saved as a measurement.')
    st.caption('Session comparison assumes the same average intensity. Training load scales with duration only as a planning approximation, not a prediction of your body’s response.')
    left,right=st.columns(2)
    changes=[]
    for col,label,initial in [(left,'A',-20),(right,'B',20)]:
        with col:
            with st.container(border=True):
                st.subheader('Path '+label)
                preset=st.radio('Session direction',['Shorter','Same session','Longer','Custom'],index=0 if label=='A' else 2,key='direction_'+label,horizontal=True)
                change={'Shorter':-20,'Same session':0,'Longer':20}.get(preset)
                if change is None:change=st.slider('Change duration (%)',-100,100,initial,5,key='change_'+label)
                values=scenario_values(duration,load,change);changes.append((change,values))
                st.metric('Session duration',f"{values['duration']:.1f} min" if values['duration'] is not None else 'Choose a starting duration',f'{change:+d}% vs starting session')
                if values['load'] is not None:st.metric('Illustrative load',f"{values['load']:.1f} AU")
    p=palette();fig=go.Figure()
    # Fixed anchor with two smooth branches: movement reflects relative duration only.
    fig.add_trace(go.Scatter(x=[0],y=[100],mode='markers',marker=dict(size=16,color=p['ink']),name='Starting session'))
    for (change,values),label,color in zip(changes,['Path A','Path B'],[p['accent'],p['low']]):
        fig.add_trace(go.Scatter(x=[0,.5,1],y=[100,100+change*.3,100+change],mode='lines+markers',line=dict(shape='spline',width=4,color=color),marker=dict(size=9),name=label,hovertemplate=label+' · %{y:.0f}% of starting duration<extra></extra>'))
    fig.update_layout(height=380,xaxis=dict(tickvals=[0,1],ticktext=['Your starting point','Your two possibilities']),yaxis_title='Relative session duration (%)')
    st.plotly_chart(style_chart(fig),theme=None,use_container_width=True,config={'displayModeBar':False})
    st.caption('The branches compare plans, not a time forecast or injury-risk curve. 100% means the same duration as your starting session.')
    st.subheader('What changes — and what stays unknown')
    if duration is not None:
        delta=changes[1][1]['duration']-changes[0][1]['duration']
        st.write(f"Path B is {abs(delta):.1f} minutes {'longer' if delta>=0 else 'shorter'} than Path A. Your saved session stays unchanged.")
    else:st.write('Choose a starting duration above to see both plans in minutes. The branches already show their relative difference.')
    required=('sleep_hours','training_load','recovery_time')
    if all(finite_value(snap.get(k)) is not None for k in required):
        with st.expander('Explore the existing fatigue-rule response'):
            from digital_twin.simulation_engine import simulate_scenario
            st.caption('Illustrative rule-based sensitivity only; not a validated fatigue forecast or injury probability. Sleep and recovery are held unchanged.')
            base=simulate_scenario(snap)
            for (change,values),label in zip(changes,['A','B']):
                result=simulate_scenario(snap,training_load_change=load*change/100)
                st.write(f"Path {label}: rule-based fatigue index {result['simulated_fatigue_score']:.1f} / 100 (starting rule index {base['simulated_fatigue_score']:.1f}).")
    else:
        st.write('Fatigue and injury changes cannot be inferred from session length alone. Your coach can review the two plans alongside sleep, recovery and your training history.')
    if st.button('Read prediction & recommendation',type='primary'):
        st.session_state.current_page='Predictions & Coach Recommendations';st.rerun()
