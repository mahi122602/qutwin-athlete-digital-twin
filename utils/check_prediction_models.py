"""Offline model check and optional original-export diagnosis. Never writes to the DB."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',type=Path,help='Optional original activity export to analyse without saving it.')
    parser.add_argument('--sleep-hours',type=float)
    parser.add_argument('--recovery-hours',type=float)
    parser.add_argument('--hydration',choices=['Low','Medium','High'])
    args=parser.parse_args()
    try:
        from research_prediction.predict import analyse,bundle,ANALYSIS_VERSION
        from prediction.assessment_inputs import with_context
        models=bundle();report=models['report']
        if report['version']!='adaptive-v3':
            raise RuntimeError('The adaptive-v3 model file was not installed. Apply the complete prediction update, including research_prediction/adaptive_models.joblib.')
        for requirement in (ROOT/'requirements_prediction.txt').read_text().splitlines():
            if '==' not in requirement or requirement.startswith('#'):continue
            package,expected=requirement.split('==',1)
            actual=importlib.metadata.version(package)
            if actual!=expected:
                raise RuntimeError(f'{package} is {actual}; this model package was verified with {expected}. Run python -m pip install -r requirements_prediction.txt in the environment used by Streamlit.')
        # These are synthetic software-check inputs, never an athlete assessment.
        one=analyse({'training_load':60},['800 m'])
        if one.get('prediction_status')!='research_estimate' or not 0<=one['fatigue_score']<=100:
            raise RuntimeError('Single-session inference check failed.')
        outside=analyse({'training_load':319.26},['800 m'])
        if 'fatigue_score' in outside:
            raise RuntimeError('Unsupported-input guard check failed.')
        partial=analyse({'training_load':319.26,'sleep_hours':7,'recovery_time':7},['800 m'])
        if partial.get('model_tier')!='sleep_rest':
            raise RuntimeError('Partial recovery model check failed.')
        print('PREDICTION MODEL CHECK PASSED')
        print('Model:',report['version'],'| Pipeline:',ANALYSIS_VERSION)
        print('Single-session inference, partial-input inference and unsupported-input handling passed.')
        print('Checks above use software-test inputs; they are not results for your activity.')
        if args.file:
            import io
            import pandas as pd
            from ingestion.workflow_loader import load_uploaded_file
            stream=io.BytesIO(args.file.read_bytes());stream.name=args.file.name
            frame,raw,_=load_uploaded_file(stream)
            eligible=frame
            if 'record_kind' in frame and frame.record_kind.eq('activity').any():
                eligible=frame[frame.record_kind.eq('activity')]
            selected=eligible.assign(_date=pd.to_datetime(eligible.timestamp,utc=True,errors='coerce')).sort_values('_date',na_position='first',kind='stable').iloc[-1]
            record=json.loads(selected.drop(labels=['_date']).to_json(date_format='iso'))
            record,context=with_context(record,{k:v for k,v in {
                'sleep_hours':args.sleep_hours,'recovery_time':args.recovery_hours,
                'hydration_level':args.hydration}.items() if v is not None})
            snapshot=analyse(record,['100 m','800 m'])
            print('\nYOUR FILE:',args.file.name)
            print('Source observations:',len(frame))
            print(json.dumps({k:snapshot[k] for k in ('prediction_status','model_tier','fatigue_score',
                'readiness_score','injury_risk','used_model_inputs','outside_training_range','missing_inputs',
                'event_basis','model_eligibility') if k in snapshot},indent=2))
            print('No database writes or AI requests were made. Scores are research estimates, not clinical assessments.')
        return 0
    except Exception as exc:
        print('PREDICTION CHECK DID NOT FINISH:',str(exc))
        print('From your actual project folder, run: python -m pip install -r requirements_prediction.txt')
        print('Then: python utils/check_prediction_models.py')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
