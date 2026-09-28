"""Run the organized tests against the packaged application."""
import argparse,os,subprocess,sys,unittest
from pathlib import Path

TESTS=Path(__file__).resolve().parent
APP=TESTS.parent
sys.path[:0]=[str(APP/'src'),str(TESTS/'unit')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ui',action='store_true');args=parser.parse_args()
    if args.ui:
        env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(APP/'src'),str(TESTS/'unit')]),PYTHONUTF8='1',FLOWERMOON_CAMS_ENABLED='0')
        failures=[]
        for script in sorted((TESTS/'ui').glob('verify_*.py')):
            try:
                subprocess.run([sys.executable,'-B',str(script)],cwd=APP,env=env,check=True,timeout=60)
            except (subprocess.CalledProcessError,subprocess.TimeoutExpired):
                failures.append(script.name)
        if failures:print('Failed UI checks: '+', '.join(failures),flush=True)
        return 1 if failures else 0
    suite=unittest.defaultTestLoader.discover(str(TESTS/'unit'))
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
