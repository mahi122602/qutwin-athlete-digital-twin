"""Start this exact extracted folder on a fresh local port."""
from pathlib import Path
import importlib.util
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE = 'QUTwin Coach Studio — 14 Oct 2026 corrected build'


def main():
    print(RELEASE)
    print('Project folder:', ROOT)
    missing = [name for name in ('streamlit','psycopg2','pandas','plotly','bcrypt','statsmodels')
               if importlib.util.find_spec(name) is None]
    if missing:
        print('Missing packages:', ', '.join(missing))
        print('Run INSTALL_REQUIREMENTS.bat in this folder, then run RUN_QUTWIN.bat again.')
        return 1
    port = None
    for candidate in range(8510, 8531):
        try:
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', candidate))
            port = candidate
            break
        except OSError:
            continue
    if port is None:
        print('Ports 8510–8530 are occupied. Close an old QUTwin app and try again.')
        return 1
    print('Open this NEW address:', f'http://localhost:{port}')
    print('This launcher uses the app.py beside this file, regardless of the previous terminal folder.')
    return subprocess.call([sys.executable, '-m', 'streamlit', 'run', str(ROOT/'app.py'),
        '--server.address', '127.0.0.1', '--server.port', str(port),
        '--server.headless', 'false'], cwd=ROOT)


if __name__ == '__main__':
    sys.exit(main())
