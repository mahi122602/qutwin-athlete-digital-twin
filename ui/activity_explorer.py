"""Progressive activity explorer: immediate charts, explanations, then data evidence."""
import logging
import math
from pathlib import Path
import pandas as pd
import streamlit as st
from services.activity_explorer import (BUILD,MEASURES,ESTIMATES,load_explorer_data,
    available_measures,describe_measure,export_table)
from ui.activity_explorer_charts import measure_chart,relationship_chart,coverage_chart,correlation_chart
from ui.studio_shell import palette


def choose(label,options,key,**kwargs):
    if st.session_state.get(key) not in options:st.session_state.pop(key,None)
    return st.selectbox(label,options,key=key,**kwargs)


def draw(fig,key):
    st.plotly_chart(fig,use_container_width=True,theme=None,key=key,
        config={'displaylogo':False,'scrollZoom':False,'toImageButtonOptions':{'format':'png','scale':2}})


def measurement_panel(frame,catalog,prefix):
    choices=available_measures(frame,catalog)
    if not choices:return
    field=choose('What would you like to explore?',choices,prefix+'measure',format_func=lambda k:catalog[k][0])
    valid=frame[field].notna();n=int(valid.sum());dated=int((valid & frame['_plot_date'].notna()).sum())
    modes=['Activity comparison']
    if dated:modes.append('Timeline')
    if n>=2:modes.append('Distribution')
    if st.session_state.get(prefix+'mode') not in modes:st.session_state.pop(prefix+'mode',None)
    mode=st.radio('Chart view',modes,horizontal=True,key=prefix+'mode',
        help='Activity comparison includes undated records. Timeline uses actual activity dates only.')
    page=1
    if mode=='Activity comparison' and n>30:
        if not 1<=st.session_state.get(prefix+'page',1)<=math.ceil(n/30):st.session_state.pop(prefix+'page',None)
        page=int(st.number_input('Chart page · 30 recorded values per page',min_value=1,max_value=math.ceil(n/30),value=1,key=prefix+'page'))
    draw(measure_chart(frame,field,mode,catalog,palette(),page=page),prefix+'measure_chart')
    with st.container(border=True):
        st.markdown('**What this tells you**')
        st.write(describe_measure(frame,field,catalog))
    if mode=='Timeline':
        st.caption(f'{dated:,} dated values shown; {n-dated:,} undated values remain available in Activity comparison. Missing measurements break the line. Date-only records do not imply a known start time.')
        if len(frame)>2000:st.caption('Large timelines display up to 2,000 evenly sampled observations per series as markers. The export contains the full selected data.')
    else:
        noun='recorded value' if n==1 else 'recorded values'
        st.caption(f'{n:,} {noun} · {len(frame)-n:,} observations without this measure. Hover over a mark for its file, activity date and source.')
    if field=='training_load':st.caption('Calculated load proxies are labelled on hover and in Technical details. Different devices may use different load scales.')


def render_activity_explorer(athlete_id,key_prefix=None,allow_date_link=False):
    prefix=key_prefix or 'ax_'+str(athlete_id)+'_'
    st.html('<style>'+Path(__file__).with_name('activity_explorer.css').read_text(encoding='utf-8')+'</style>')
    try:data=load_explorer_data(str(athlete_id))
    except Exception as exc:
        logging.getLogger(__name__).exception('Activity explorer data read failed')
        from ui.workflow_errors import show_workflow_error
        show_workflow_error(exc,'Visualisations');return
    if data.observations.empty and data.estimates.empty:
        st.info('Your explorer starts with a saved activity. Add a file in Add activity to see its measurements here.');return
    options=['all']+[item['key'] for item in data.uploads]
    labels={item['key']:f"{item['filename']} · {item['count']:,} source observations" for item in data.uploads}
    selection=choose('Explore saved data',options,prefix+'upload',format_func=lambda key:'All saved activities' if key=='all' else labels[key])
    observed=data.observations.copy();estimated=data.estimates.copy()
    if selection!='all':
        if not observed.empty:observed=observed[observed['_upload_key'].eq(selection)]
        if not estimated.empty:estimated=estimated[estimated['_upload_key'].eq(selection)]
    measured=available_measures(observed);predicted=available_measures(estimated,ESTIMATES)
    if not measured and not predicted:
        st.info('This saved file has no recognised numeric measurements yet. Review its source columns and units in Add activity.');return
    dated=int(observed['_plot_date'].notna().sum()) if not observed.empty else 0
    noun='saved observation' if len(observed)==1 else 'saved observations'
    st.html('<div data-explorer-build="'+BUILD+'" class="ax-intro"><span class="ax-pill">'+
        f'{len(observed):,} {noun}</span><span class="ax-pill">{dated:,} with an activity date</span>'+
        '<strong>'+('Your data is ready to explore.' if dated else 'Your measurements are visible, even without a date.')+
        '</strong><p>'+('Start with an activity comparison. Switch to Timeline for known activity dates, or open Technical details to inspect sources and missing values.' if dated else
        'The charts below use activity labels. Add a known activity date when available to unlock a timeline; you can explore the recorded values now.')+'</p></div>')
    with st.container(key=prefix+'metrics'):
        cols=st.columns(4)
        activities=observed[observed['_kind'].ne('measurement')] if not observed.empty else observed
        cols[0].metric('Activity records',f'{len(activities):,}')
        for col,field,label,unit in [(cols[1],'duration_minutes','Recorded duration','min'),(cols[2],'distance','Recorded distance','km')]:
            values=activities[field].dropna() if field in activities else pd.Series(dtype=float)
            col.metric(label,f'{values.sum():,.1f} {unit}' if len(values) else 'Not recorded')
        cols[3].metric('Available measures',len(measured))
    overview,compare,technical=st.tabs(['Understand your activity','Compare measurements','Technical details'])
    with overview:
        if measured:
            measurement_panel(observed,MEASURES,prefix+'observed_')
        if predicted:
            st.subheader('Model estimates')
            st.caption('These are saved research outputs, separate from source measurements. Readiness and composite scores are calculated indices; none establishes an injury probability or clearance to train.')
            measurement_panel(estimated,ESTIMATES,prefix+'estimated_')
        elif measured:
            st.caption('No numeric model estimate is saved for this selection. Your recorded measurements remain charted. Prediction & recommendation explains model-input requirements.')
        if allow_date_link and not dated and len(data.uploads):
            target=selection if selection!='all' else data.uploads[0]['key'] if len(data.uploads)==1 else None
            if target is not None and target!='legacy' and st.button('Add a known activity date',key=prefix+'date_link'):
                st.session_state.studio_target_upload=target
                st.session_state.current_page='Predictions & Coach Recommendations';st.rerun()
    with compare:
        st.subheader('How do two measurements compare?')
        st.write('Each dot represents one saved observation with both measurements. Dates are optional for this view.')
        if len(measured)>=2:
            a,b=st.columns(2)
            with a:x=choose('Horizontal axis',measured,prefix+'x',format_func=lambda key:MEASURES[key][0])
            with b:y=choose('Vertical axis',[key for key in measured if key!=x],prefix+'y',format_func=lambda key:MEASURES[key][0])
            pairs=observed.dropna(subset=[x,y]);n=len(pairs)
            if n:
                draw(relationship_chart(observed,x,y,palette()),prefix+'relationships')
                if n==1:st.info('This dot shows the two values in your one recorded observation. More paired observations are needed to describe a relationship.')
                else:st.caption(f'{n:,} paired observations · a pattern does not prove that one measurement causes another.')
                if n>2000:st.caption('The chart displays 2,000 evenly sampled pairs. All pairs are retained in the data export.')
            else:st.info('Both measures exist, but they were not recorded together in the same observation. Select another pair.')
        else:
            st.info('A comparison needs two numeric measurements in the same observation. Your available measure is already charted in Understand your activity.')
            if not observed.empty:draw(coverage_chart(observed,palette()),prefix+'comparison_coverage')
    with technical:
        st.subheader('Data coverage and provenance')
        st.caption(f'Build {BUILD} · exact source values and athlete-confirmed context · upload times are never used as activity dates.')
        if not observed.empty:
            draw(coverage_chart(observed,palette()),prefix+'coverage')
            st.caption('Value available means a usable recorded, confirmed or explicitly derived value. Not recorded means missing, not zero.')
            table=export_table(observed)
            st.dataframe(table.head(1000),hide_index=True,use_container_width=True)
            st.download_button('Download selected measurements (CSV)',table.to_csv(index=False).encode('utf-8-sig'),
                'QUTwin_selected_measurements.csv','text/csv',key=prefix+'csv')
            if len(table)>1000:st.caption('Preview: first 1,000 observations. Download includes every selected observation.')
            with st.expander('Descriptive correlations · at least five paired observations'):
                fig=correlation_chart(observed,palette())
                if fig is not None:
                    draw(fig,prefix+'correlations')
                    st.caption('Pearson correlation uses observed pairs only, with their counts on hover. It is descriptive, not evidence of cause or a validated prediction. A calculated load proxy is mathematically linked to its input measurements.')
                else:st.info('At least two varying measurements with five paired observations are needed. No correlation is invented from a single activity.')
        if predicted:
            st.markdown('**Saved model outputs and versions**')
            table=export_table(estimated,ESTIMATES)
            st.dataframe(table.head(1000),hide_index=True,use_container_width=True)
            st.download_button('Download selected model outputs (CSV)',table.to_csv(index=False).encode('utf-8-sig'),
                'QUTwin_selected_model_outputs.csv','text/csv',key=prefix+'model_csv')
            st.caption('Different model versions, input tiers and event references form separate timeline series. Outputs are not replicated across every raw sensor observation.')
        if data.rejected_values:st.warning(f'Across the loaded uploads, {data.rejected_values:,} non-numeric or out-of-range values were excluded from numeric charts. Check source columns and units before interpreting the data.')
