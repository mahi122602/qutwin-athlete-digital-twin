"""A journal story built from saved summaries, including undated activities."""
from html import escape
import math
from pathlib import Path
import pandas as pd
import streamlit as st
from services.activity_explorer import (MEASURES, ESTIMATES, available_measures,
    build_explorer_data, describe_measure)
from ui.activity_explorer import choose, draw
from ui.activity_explorer_charts import measure_chart
from ui.studio_shell import palette

BUILD = 'performance-story-2026-10-21'
PREFERRED = ('duration_minutes', 'distance', 'heart_rate', 'steps', 'training_load',
             'sleep_hours', 'recovery_time', 'calories')


def journal_data(frame):
    """One observation per saved upload; saving a file never dates its activity."""
    uploads = []
    rows = frame.astype(object).where(frame.notna(), None).to_dict('records')
    for index, row in enumerate(rows):
        uploads.append(dict(id=str(index), filename=row.get('filename') or 'Saved activity',
            uploaded_at=row.get('_uploaded_at'), snapshot=row, records=[{'record_kind':'activity'}]))
    data = build_explorer_data(uploads)
    if not data.observations.empty:
        data.observations['_origin'] = 'Saved activity summary'
    for table in (data.observations, data.estimates):
        if not table.empty:
            table['_story_label'] = [f"{int(key)+1:02d} · {str(name)[:34]}"
                                    for key, name in zip(table['_upload_key'], table['_filename'])]
    return data


def ordered_fields(frame, catalog=MEASURES):
    fields = available_measures(frame, catalog)
    return [field for field in PREFERRED if field in fields] + [field for field in fields if field not in PREFERRED]


def story_figure(frame, field, mode, catalog=MEASURES, selected='0', page=1):
    """Reuse the explorer's date/coverage rules; highlight without ranking uploads."""
    p = palette()
    fig = measure_chart(frame, field, mode, catalog, p, page=page)
    if mode == 'Activity comparison' and fig.data:
        shown = frame[frame[field].notna()].iloc[(page-1)*30:page*30]
        fig.data[0].y = [escape(str(label)) for label in shown['_story_label']]
        fig.data[0].marker.color = [p['accent'] if key == selected else p['low'] for key in shown['_upload_key']]
        fig.update_layout(title=None, margin=dict(t=24))
    return fig


def show_spotlight(observation, catalog, fields):
    cards = []
    for field in fields[:3]:
        label, unit, _ = catalog[field]
        value = float(observation[field])
        display = f'{value:,.0f}' if field in ('steps', 'calories') else f'{value:,.1f}'
        cards.append('<article class="ps-value"><span>'+escape(label)+'</span><strong>'+display+
                     '<small>'+escape(unit)+'</small></strong></article>')
    if cards:
        st.html('<div class="ps-values">'+''.join(cards)+'</div>')
    else:
        st.info('This file is saved, but its summary has no usable numeric measurements yet. Open Visualisations to check all source records, or review its column mapping in Add activity.')


def render_performance_story(frame, data=None):
    data = data if data is not None else journal_data(frame)
    observed, estimated = data.observations, data.estimates
    if observed.empty:
        return
    prefix = 'ps_' + str(st.session_state.get('user_id', 'athlete')) + '_'
    st.html('<style>'+Path(__file__).with_name('performance_story.css').read_text(encoding='utf-8')+'</style>')
    count = len(frame)
    dated = int(observed['_plot_date'].notna().sum())
    description = ('Compare your saved activity summaries now. Add known activity dates whenever you have them to see your story over time.'
                   if not dated else 'Compare your saved activity summaries, or switch to Over time to explore activities with known dates.')
    track = '<div class="ps-track" aria-hidden="true"><i></i><i></i><i></i><b></b></div>'
    st.html('<section class="ps-hero" data-story-build="'+BUILD+'"><div><span class="ps-eyebrow">YOUR PERFORMANCE STORY</span>'+
        '<h2>See the story in your sessions.</h2><p>'+description+'</p><span class="ps-chip">'+str(count)+
        (' saved upload' if count == 1 else ' saved uploads')+'</span><span class="ps-chip">'+
        ('Compare without dates' if not dated else str(dated)+' with an activity date')+'</span></div>'+track+'</section>')

    with st.container(border=True, key=prefix+'spotlight'):
        st.markdown('### Activity spotlight')
        st.caption('Choose a saved upload to see its recorded summary. The first item is the most recently saved file, not necessarily the most recent activity.')
        options = [str(i) for i in range(len(frame))]
        names = [str(name or 'Saved activity') for name in frame.get('filename', pd.Series('Saved activity', index=frame.index)).fillna('Saved activity')]
        selected = choose('Choose a saved activity', options, prefix+'activity',
                          format_func=lambda key: f'{int(key)+1:02d} · {names[int(key)]}')
        current = observed[observed['_upload_key'].eq(selected)]
        row = current.iloc[0]
        fields = ordered_fields(current)
        st.caption('Activity date: '+str(row['_date_label']))
        show_spotlight(row, MEASURES, fields)

    measured = ordered_fields(observed)
    predicted = ordered_fields(estimated, ESTIMATES)
    if measured or predicted:
        with st.container(border=True, key=prefix+'comparison'):
            st.markdown('### Put your activities side by side')
            groups = (['Recorded measurements'] if measured else []) + (['Research estimates'] if predicted else [])
            group = choose('Explore', groups, prefix+'group') if len(groups)>1 else groups[0]
            table, catalog = (observed, MEASURES) if group == 'Recorded measurements' else (estimated, ESTIMATES)
            fields = ordered_fields(table, catalog)
            field = choose('What would you like to compare?', fields, prefix+'measure', format_func=lambda key: catalog[key][0])
            valid = table[field].notna()
            known = int((valid & table['_plot_date'].notna()).sum())
            modes = ['Activity comparison'] + (['Timeline'] if known else [])
            if st.session_state.get(prefix+'view') not in modes:
                st.session_state.pop(prefix+'view', None)
            mode = st.radio('View your story', modes, key=prefix+'view', horizontal=True,
                format_func=lambda key: 'Compare activities' if key == 'Activity comparison' else 'Over time') if len(modes)>1 else modes[0]
            page = 1
            n = int(valid.sum())
            if mode == 'Activity comparison' and n>30:
                pages = math.ceil(n/30)
                if not 1 <= st.session_state.get(prefix+'page', 1) <= pages:
                    st.session_state.pop(prefix+'page', None)
                page = int(st.number_input('Chart page · 30 summaries per page', min_value=1, max_value=pages, value=1, key=prefix+'page'))
            draw(story_figure(table, field, mode, catalog, selected, page), prefix+'chart')
            st.html('<div class="ps-takeaway"><span>WHAT THIS TELLS YOU</span><p>'+escape(describe_measure(table, field, catalog))+'</p></div>')
            if mode == 'Activity comparison':
                st.caption('One bar per saved summary with this value. Your selected activity uses the accent colour when its value is available. Order follows when files were saved; it is not a performance ranking or a time trend.')
            else:
                st.caption(f'{known} dated summaries shown. {n-known} undated summaries remain in Compare activities. Missing measurements break the line; upload times are never used as activity dates.')
            if group == 'Research estimates':
                st.caption('Saved model outputs, not measured performance. Model versions, input tiers and event references form separate timeline series. Readiness is a calculated index, not clearance to train.')

    a, b = st.columns(2)
    with a:
        with st.container(border=True, key=prefix+'next'):
            missing = pd.isna(row['_plot_date'])
            st.markdown('#### '+('Give this session its place in time' if missing else 'A date adds the time perspective'))
            st.write('Your recorded values are already visible. A known activity date adds this session to the timeline.' if missing else
                     'This session has an activity date. Choose Over time when your selected measure has dated values.')
            target = frame.iloc[int(selected)].get('workflow_id')
            if missing and target is not None and pd.notna(target):
                if st.button('Review activity & add its date', key=prefix+'date', use_container_width=True):
                    st.session_state.studio_target_upload = str(int(target)) if isinstance(target, float) and target.is_integer() else str(target)
                    st.session_state.current_page = 'Predictions & Coach Recommendations'
                    st.rerun()
            elif missing:
                st.caption('Add the actual activity dates from a source you trust. Older unlinked files can be reviewed in Add activity.')
    with b:
        with st.container(border=True, key=prefix+'explore'):
            st.markdown('#### Look beyond the summary')
            st.write('Visualisations opens every saved source observation, more measures, comparisons and downloads.')
            if st.button('Explore all measurements', key=prefix+'explore_button', use_container_width=True):
                st.session_state.current_page = 'Visualisations / Graphs'
                st.rerun()
    with st.expander('How your performance story works'):
        st.write('This view uses one saved summary per upload. A ZIP or sensor export can contain many source records; open Visualisations to inspect them all. Empty values remain unknown, and no score or date is invented.')
        st.write('Activities with known dates can appear on a timeline. Date-only records are labelled as such. Different devices may use different activity-load scales, so their load numbers should not automatically be treated as equivalent.')
        st.caption('Build '+BUILD)
