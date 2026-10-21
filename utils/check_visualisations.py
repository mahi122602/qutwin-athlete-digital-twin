"""Offline visualisation checks; optionally inspect an original export without saving."""
import argparse
import io
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',type=Path,help='Optional original activity file to inspect locally.')
    args=parser.parse_args()
    try:
        from services.activity_explorer import BUILD,MEASURES,build_explorer_data,available_measures
        from ui.activity_explorer_charts import measure_chart,relationship_chart
        example={'id':'software-check','filename':'Software-check values','records':[{'heart_rate':150,'duration_minutes':40}],'snapshot':{}}
        data=build_explorer_data([example]);frame=data.observations
        bar=measure_chart(frame,'heart_rate')
        assert bar.data[0].type=='bar' and float(bar.data[0].x[0])==150
        assert frame['_plot_date'].isna().all()
        assert len(relationship_chart(frame,'heart_rate','duration_minutes').data[0].x)==1
        example['records'][0]['activity_date_only']='2026-10-01'
        dated=build_explorer_data([example]).observations
        assert dated['_date_precision'].iloc[0]=='Date only'
        assert len(measure_chart(dated,'heart_rate','Timeline').data[0].x)==1
        print('VISUALISATION CHECK PASSED')
        print('Build:',BUILD)
        print('One undated activity, real-value bar, comparison point and date-only timeline passed.')
        print('These checks use software-test values, not your activity results.')
        if args.file:
            from ingestion.workflow_loader import load_uploaded_file
            stream=io.BytesIO(args.file.read_bytes());stream.name=args.file.name
            source,reports,_=load_uploaded_file(stream)
            records=json.loads(source.to_json(orient='records',date_format='iso'))
            data=build_explorer_data([dict(id='local-file',filename=args.file.name,records=records,snapshot={})])
            choices=available_measures(data.observations)
            print('\nYour file:',args.file.name)
            print('Saved source observations:',len(data.observations))
            print('Known activity dates:',int(data.observations['_plot_date'].notna().sum()))
            print('Available measures:',', '.join(MEASURES[key][0] for key in choices) or 'None recognised')
            if not choices:
                print('Review the source columns and confirm units in Add activity. No numbers were invented.')
                return 1
            print('Default chart:',measure_chart(data.observations,choices[0]).data[0].type)
        print('No database writes, AI requests or model changes were made.')
        return 0
    except Exception as exc:
        print('VISUALISATION CHECK DID NOT FINISH:',str(exc))
        print('Apply the complete visualisation update. From the actual project folder, run:')
        print('python -m pip install -r requirements.txt')
        print('python utils/check_visualisations.py')
        return 1


if __name__=='__main__':raise SystemExit(main())
