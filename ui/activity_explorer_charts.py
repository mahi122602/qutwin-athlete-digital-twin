"""Charts in real units, with explicit dates, sources and model groups."""
import math
from html import escape
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from services.activity_explorer import MEASURES,ESTIMATES,available_measures,value_sources

DEFAULT={'bg':'#fcfaf4','panel':'#fffdf8','ink':'#193e38','muted':'#52675e',
         'line':'#d7dfd3','soft':'#edf1e7','accent':'#925b37','low':'#416b52'}


def finish(fig,p=None,height=420):
    p=p or DEFAULT
    fig.update_layout(template='plotly_white',paper_bgcolor=p['panel'],plot_bgcolor=p['panel'],
        font=dict(family='Arial, sans-serif',size=16,color=p['ink']),height=height,
        margin=dict(l=35,r=45,t=48,b=55),legend=dict(orientation='h',y=-.2),
        hoverlabel=dict(bgcolor=p['panel'],font_color=p['ink'],font_size=15,bordercolor=p['line']))
    fig.update_xaxes(color=p['ink'],gridcolor=p['line'],zerolinecolor=p['line'],automargin=True)
    fig.update_yaxes(color=p['ink'],gridcolor=p['line'],zerolinecolor=p['line'],automargin=True)
    return fig


def custom_rows(frame,field):
    sources=value_sources(frame,field)
    return [[escape(str(row['_filename'])),escape(str(row['_date_label'])),escape(str(sources.loc[index])),
             escape(str(row.get('_record_key','')))] for index,row in frame.iterrows()]


def evenly_sample(frame,limit=2000):
    if len(frame)<=limit:return frame
    # Display sampling never creates/changes a value. Full data remains exportable.
    positions=np.unique(np.linspace(0,len(frame)-1,limit,dtype=int))
    return frame.iloc[positions]


def measure_chart(frame,field,mode='Activity comparison',catalog=MEASURES,p=None,page=1,page_size=30):
    p=p or DEFAULT;label,unit,_=catalog[field];fig=go.Figure()
    valid=frame[frame[field].notna()].copy()
    if mode=='Distribution':
        fig.add_trace(go.Histogram(x=valid[field],name='Recorded observations',marker_color=p['low'],
            nbinsx=min(20,max(2,int(math.sqrt(len(valid))))),hovertemplate=f'{escape(label)}: %{{x}} {unit}<br>Observations: %{{y}}<extra></extra>'))
        fig.update_layout(xaxis_title=f'{label} ({unit})',yaxis_title='Number of recorded observations',bargap=.08)
    elif mode=='Timeline':
        dated=frame[frame['_plot_date'].notna()].sort_values('_plot_date',kind='stable')
        if not dated[field].notna().any():
            return measure_chart(frame,field,'Activity comparison',catalog,p,page,page_size)
        if catalog is ESTIMATES:
            groups=dated.groupby(['_model_version','_model_tier','_primary_event'],dropna=False,sort=False)
        elif field=='training_load':
            dated=dated.copy()
            origins=value_sources(dated,field)
            dated['_load_series']=['QUTwin HR-duration proxy' if origin=='Calculated load proxy' else 'Imported load · file #'+str(key)
                                   for origin,key in zip(origins,dated['_upload_key'])]
            groups=dated.groupby('_load_series',sort=False)
        else:groups=[('Recorded measurements',dated)]
        colors=[p['low'],p['accent'],p['muted']]
        for index,(name,group) in enumerate(groups):
            shown=evenly_sample(group)
            # Large timelines show sampled markers only; sampled-out gaps are never joined.
            mode_name='lines+markers' if len(group)<=2000 and len(group)>1 else 'markers'
            fig.add_trace(go.Scatter(x=shown['_plot_date'],y=shown[field],mode=mode_name,
                name=' · '.join(map(str,name)) if isinstance(name,tuple) else name,
                connectgaps=False,line=dict(color=colors[index%len(colors)],width=2.5),
                marker=dict(size=9,color=colors[index%len(colors)],line=dict(color=p['panel'],width=1)),
                customdata=custom_rows(shown,field),
                hovertemplate=f'%{{customdata[0]}}<br>%{{customdata[1]}}<br>{escape(label)}: %{{y:.2f}} {unit}<br>%{{customdata[2]}}<extra></extra>'))
        fig.update_layout(xaxis_title='Recorded activity date · UTC for known times',yaxis_title=f'{label} ({unit})')
    else:
        start=(page-1)*page_size;shown=valid.iloc[start:start+page_size]
        values=shown[field]
        sources=value_sources(shown,field)
        color_map={'Source export':p['low'],'Athlete confirmed':p['accent'],
                   'Calculated load proxy':p['muted'],'Legacy saved measurement':p['low'],'Research estimate':p['accent']}
        single_file=valid['_upload_key'].nunique()==1
        labels=[]
        for _,row in shown.iterrows():
            if catalog is ESTIMATES:label_text='Assessment #'+str(row['_upload_key'])
            else:
                noun='Measurement' if row.get('_kind')=='measurement' else 'Activity'
                label_text=noun+' '+str(row['_record_key']).split(':')[-1]
                if not single_file:label_text+=' · file #'+str(row['_upload_key'])
            labels.append(escape(label_text))
        fig.add_trace(go.Bar(x=values,y=labels,orientation='h',
            marker_color=[color_map.get(source,p['low']) for source in sources],
            text=[f'{value:,.1f} {unit}' for value in values],textposition='outside',cliponaxis=False,
            customdata=custom_rows(shown,field),name=label,
            hovertemplate=f'%{{customdata[0]}}<br>%{{customdata[1]}}<br>{escape(label)}: %{{x:.2f}} {unit}<br>%{{customdata[2]}}<extra></extra>'))
        fig.update_layout(xaxis_title=f'{label} ({unit})',yaxis_title='',showlegend=False)
        fig.update_yaxes(autorange='reversed')
        if len(values):
            minimum=float(values.min());maximum=float(values.max())
            fig.update_xaxes(range=[min(0,minimum*1.2),max(1,maximum*1.28)])
        finish(fig,p,height=min(750,max(280,len(shown)*31+130)))
    if mode!='Activity comparison':finish(fig,p)
    if catalog is ESTIMATES:
        if mode=='Timeline':fig.update_yaxes(range=[0,100])
        elif mode=='Activity comparison':fig.update_xaxes(range=[0,110])
    fig.update_layout(title=dict(text=label,font_size=20))
    return fig


def relationship_chart(frame,x,y,p=None,catalog=MEASURES):
    p=p or DEFAULT
    pairs=frame.dropna(subset=[x,y])
    shown=evenly_sample(pairs)
    fig=go.Figure()
    custom=[[escape(str(row['_filename'])),escape(str(row['_date_label'])),escape(str(row['_record_key']))]
            for _,row in shown.iterrows()]
    fig.add_trace(go.Scatter(x=shown[x],y=shown[y],mode='markers',name='Recorded observation',
        marker=dict(size=13,color=p['low'],opacity=.85,line=dict(color=p['panel'],width=1.5)),customdata=custom,
        hovertemplate=f'%{{customdata[0]}}<br>%{{customdata[1]}}<br>{catalog[x][0]}: %{{x:.2f}} {catalog[x][1]}<br>{catalog[y][0]}: %{{y:.2f}} {catalog[y][1]}<extra></extra>'))
    fig.update_layout(xaxis_title=f'{catalog[x][0]} ({catalog[x][1]})',
                      yaxis_title=f'{catalog[y][0]} ({catalog[y][1]})',showlegend=False)
    return finish(fig,p)


def coverage_chart(frame,p=None):
    p=p or DEFAULT
    fields=[k for k in ('heart_rate','duration_minutes','distance','training_load','sleep_hours','recovery_time','temperature','humidity') if k in frame]
    known=[int(frame[key].notna().sum()) for key in fields]
    missing=[len(frame)-value for value in known]
    labels=[MEASURES[key][0] for key in fields]
    fig=go.Figure()
    fig.add_trace(go.Bar(y=labels,x=known,name='Value available',orientation='h',marker_color=p['low'],
        text=[str(n) if n else '' for n in known],textposition='auto',hovertemplate='%{y}<br>Available: %{x}<extra></extra>'))
    fig.add_trace(go.Bar(y=labels,x=missing,name='Not recorded',orientation='h',marker_color=p['soft'],
        marker_line=dict(color=p['line'],width=1),hovertemplate='%{y}<br>Not recorded: %{x}<extra></extra>'))
    fig.update_layout(barmode='stack',xaxis_title='Saved observations · missing values are not zeros',yaxis_title='')
    fig.update_xaxes(dtick=1 if len(frame)<10 else None)
    fig.update_yaxes(autorange='reversed')
    return finish(fig,p,height=400)


def correlation_chart(frame,p=None):
    p=p or DEFAULT
    fields=[k for k in available_measures(frame) if frame[k].notna().sum()>=5 and frame[k].nunique()>1]
    if len(fields)<2:return None
    values=frame[fields];correlation=values.corr(min_periods=5)
    counts=values.notna().astype(int).T.dot(values.notna().astype(int))
    off_diagonal=correlation.to_numpy().copy()
    np.fill_diagonal(off_diagonal,np.nan)
    if not np.isfinite(off_diagonal).any():return None
    labels=[MEASURES[key][0] for key in fields]
    z=correlation.to_numpy()
    fig=go.Figure(go.Heatmap(x=labels,y=labels,z=z,zmin=-1,zmax=1,
        customdata=counts.to_numpy(),colorscale=[[0,p['low']],[.5,p['panel']],[1,p['accent']]],
        hoverongaps=False,hovertemplate='%{x} × %{y}<br>Pearson r: %{z:.2f}<br>Paired observations: %{customdata}<extra></extra>',
        colorbar=dict(title='Pearson r',tickvals=[-1,0,1])))
    for r,row in enumerate(z):
        for c,value in enumerate(row):
            if np.isfinite(value):fig.add_annotation(x=labels[c],y=labels[r],text=f'{value:.2f}',showarrow=False,
                font=dict(size=14,color=p['panel'] if abs(value)>.55 else p['ink']))
    fig.update_yaxes(autorange='reversed')
    return finish(fig,p,height=max(420,len(fields)*45+160))
