"""Run with python -m utils.check_workflow from the app directory."""
import importlib
import sys


def main():
    packages=('streamlit','pandas','psycopg2','plotly','defusedxml','fitparse','openpyxl','xlrd','sklearn','joblib','catboost')
    missing=[]
    for name in packages:
        try: importlib.import_module(name)
        except ImportError: missing.append(name)
    if missing:
        print('Missing packages: '+', '.join(missing))
        print('Run: python -m pip install -r requirements.txt')
        return 1
    print('Required Python packages: OK')
    import sklearn
    if sklearn.__version__ != '1.6.1':
        print('Install the pinned scikit-learn 1.6.1 from requirements.txt before loading the bundled research model.')
        return 1
    from research_prediction.predict import bundle
    bundle()
    from research_prediction.predict import analyse
    result=analyse({'training_load':60},['800 m'])
    if result.get('prediction_status')!='research_estimate':
        print('Bundled model smoke check failed.');return 1
    if '--offline' in sys.argv:
        print('Offline checks passed: imports, bundled models and partial-input prediction. No database or AI request was made.');return 0
    print('Research model artifact: OK (experimental estimates)')
    from database.workflow_schema import get_connection, WorkflowSetupError
    conn=None
    try:
        conn=get_connection()
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM qutwin_processed_uploads LIMIT 0')
            cur.execute('SELECT id FROM qutwin_recommendation_reviews LIMIT 0')
        print('Database connection and workflow schema: OK')
        print('No athlete records were inserted or modified by this check.')
        from recommendation.llm_service import setting
        if not setting('GEMINI_API_KEY') or not setting('QUTWIN_GEMINI_MODEL'):
            print('AI generation is not configured; uploads and History can still work.')
        else:
            print('Gemini settings present (no API request was made).')
        return 0
    except Exception as exc:
        code=getattr(exc,'pgcode',None) or getattr(exc,'code',None)
        print(f'Workflow check failed: {type(exc).__name__}; code={code or "not supplied"}')
        if isinstance(exc,WorkflowSetupError): print(str(exc))
        else: print('Check database access and connection settings. No credentials are printed by this check.')
        return 1
    finally:
        if conn is not None: conn.close()


if __name__=='__main__':
    sys.exit(main())
