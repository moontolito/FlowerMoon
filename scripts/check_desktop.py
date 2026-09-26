"""Check noVNC HTTP service and a real mapped FlowerMoon window in the container."""
import subprocess,time
from urllib.request import urlopen

for attempt in range(60):
    try:
        with urlopen('http://127.0.0.1:6080/',timeout=5) as response:
            assert response.status==200
            assert b'novnc' in response.read().lower()
        windows=subprocess.check_output(['xwininfo','-root','-tree'],text=True)
        assert 'FlowerMoon' in windows
        print('PASS: noVNC HTTP and automatically launched FlowerMoon window')
        break
    except (OSError,AssertionError,subprocess.CalledProcessError):
        if attempt==59:raise
        time.sleep(1)
