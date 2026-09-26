"""Check noVNC HTTP service and a real mapped FlowerMoon window in the container."""
import subprocess,time,re,json
from pathlib import Path
from urllib.request import urlopen
from PIL import ImageGrab

artifacts=Path(__file__).resolve().parents[1]/'.artifacts'
artifacts.mkdir(exist_ok=True)

for attempt in range(60):
    try:
        with urlopen('http://127.0.0.1:6080/',timeout=5) as response:
            assert response.status==200
            assert b'novnc' in response.read().lower()
        windows=subprocess.check_output(['xwininfo','-root','-tree'],text=True)
        match=re.search(r'(0x[0-9a-f]+) "FlowerMoon[^\n]*',windows)
        assert match,'No FlowerMoon window exists'
        info=subprocess.check_output(['xwininfo','-id',match[1]],text=True)
        assert 'Map State: IsViewable' in info,'FlowerMoon window is not viewable'
        left=int(re.search(r'Absolute upper-left X:\s+(-?\d+)',info)[1])
        top=int(re.search(r'Absolute upper-left Y:\s+(-?\d+)',info)[1])
        width=int(re.search(r'Width:\s+(\d+)',info)[1]);height=int(re.search(r'Height:\s+(\d+)',info)[1])
        screenshot=ImageGrab.grab()
        screenshot.save(artifacts/'desktop.png')
        app=screenshot.crop((left,top,left+width,top+height)).convert('RGB')
        app.save(artifacts/'transport.png');app.thumbnail((320,240))
        pixels=list(app.getdata());not_white=sum(min(p)<230 for p in pixels)/len(pixels)
        report={'window':match[0],'width':width,'height':height,'nonWhiteFraction':not_white}
        (artifacts/'render-check.json').write_text(json.dumps(report,indent=2))
        assert not_white>.08,'FlowerMoon is mapped but its rendered image is blank/white'
        print('PASS: noVNC HTTP, mapped FlowerMoon window and nonblank rendered pixels',report)
        break
    except (OSError,AssertionError,subprocess.CalledProcessError):
        if attempt==59:raise
        time.sleep(1)
