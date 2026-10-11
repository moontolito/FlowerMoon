"""FlowerMoon Transport for the browser: JSON API + static page, no desktop streaming.

Run locally:  uvicorn webapp.server:app --port 8000   (from apps/transport)
"""
import io
import logging
import os
import re
import secrets
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

os.environ.setdefault('FLOWERMOON_CAMS_ENABLED', '0')  # optional ADS corrosivity is not exposed in the web MVP

from fastapi import FastAPI, HTTPException, Request, Response  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from webapp import workspace as ws  # noqa: E402

ROOT = Path(__file__).resolve().parent
APP_ROOT = ROOT.parent
DATA = Path(os.environ.get('FLOWERMOON_WEB_DATA', APP_ROOT / 'data' / 'web'))
COOKIE = 'fm_session'
MAX_SESSIONS = int(os.environ.get('FLOWERMOON_WEB_SESSIONS', '40'))
log = logging.getLogger('flowermoon.web')


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm_seismic, daemon=True).start()
    yield


app = FastAPI(title='FlowerMoon Transport', docs_url='/api/docs', redoc_url=None, lifespan=lifespan)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='sources')
_sessions = OrderedDict()
_sessions_lock = threading.Lock()


def _warm_seismic():
    try:
        ws.gem_hazard.metadata()
        log.info('GEM seismic raster verified.')
    except Exception as error:  # the page still works; PGA shows as unavailable
        log.warning('GEM seismic raster unavailable: %s', error)


def session(request: Request, response: Response):
    sid = request.cookies.get(COOKIE, '')
    if not re.fullmatch(r'[0-9a-f]{32}', sid):
        sid = secrets.token_hex(16)
    with _sessions_lock:
        workspace = _sessions.get(sid)
        if workspace is None:
            workspace = ws.Workspace(DATA / 'sessions' / sid / 'planning.json', DATA / 'cache', _pool)
            _sessions[sid] = workspace
            while len(_sessions) > MAX_SESSIONS:
                _sessions.popitem(last=False)
        _sessions.move_to_end(sid)
    response.set_cookie(COOKIE, sid, max_age=60 * 60 * 24 * 30, httponly=True, samesite='lax',
                        secure=request.url.scheme == 'https')
    return workspace


@app.exception_handler(ValueError)
def value_error(_request, error):
    return JSONResponse({'detail': str(error)}, status_code=400)


@app.get('/', include_in_schema=False)
def index():
    return FileResponse(ROOT / 'static' / 'index.html', headers={'Cache-Control': 'no-cache'})


@app.get('/logo.png', include_in_schema=False)
def logo():
    return FileResponse(APP_ROOT / 'assets' / 'FlowerMoonLogo.png', headers={'Cache-Control': 'max-age=86400'})


@app.get('/healthz', include_in_schema=False)
def health():
    return {'ok': True}


@app.get('/api/state')
def state(request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        return w.snapshot()


@app.get('/api/places')
def search_places(q: str):
    return ws.places.search(q.strip()[:200])


@app.post('/api/locations')
def set_locations(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.set_locations(body.get('originName', ''), body.get('originCoords', ''),
                        body.get('destinationName', ''), body.get('destinationCoords', ''), body.get('via', ''))
        return w.snapshot()


@app.post('/api/locations/reverse')
def reverse(body: dict, request: Request, response: Response):
    """Find a mapped address for a clicked point; the selected coordinates never move."""
    w = session(request, response)
    target = 'origin' if body.get('target') == 'origin' else 'destination'
    with w.lock:
        coords = w.origin_coords if target == 'origin' else w.dest_coords
    point = ws.coordinates(coords)
    record = ws.reverse_record(target, coords, point)
    with w.lock:
        w.apply_label(target, record)
        return w.snapshot()


@app.post('/api/product')
def set_product(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.set_product(body)
        return w.snapshot()


@app.post('/api/vehicle/preset')
def select_preset(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.select_preset(str(body.get('id', '')))
        return w.snapshot()


@app.post('/api/vehicle/recommend')
def recommend(request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.choose_recommended()
        w.status = 'Recommended vehicle restored for the product.'
        return w.snapshot()


@app.post('/api/vehicle/adjust')
def adjust(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.adjust(body)
        return w.snapshot()


@app.post('/api/route')
def calculate_route(body: dict, request: Request, response: Response):
    """Explicit route (needs vehicle confirmation) or automatic preliminary route.

    A preliminary route is requested by the page after a location change, like the
    desktop app; its failures are recorded for Site & Environment, not raised.
    """
    w = session(request, response)
    preliminary = bool(body.get('preliminary'))
    with w.lock:
        if preliminary and w.route_context:
            return w.snapshot()
        try:
            payload, context, generation, server = w.route_payload(bool(body.get('confirmed')), preliminary)
        except ValueError:
            if preliminary:
                return w.snapshot()
            raise
    try:
        results = ws.route(server, payload)  # slow network call, outside the session lock
    except ValueError as error:
        with w.lock:
            w.route_failed(str(error), generation)
            if preliminary:
                return w.snapshot()
        raise
    with w.lock:
        if preliminary and w.route_context:
            return w.snapshot()  # an explicit route finished first
        try:
            w.finish_route(results, context, generation)
        except ValueError:
            if not preliminary:
                raise
        return w.snapshot()


@app.post('/api/route/select')
def select_route(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.select_route(int(body.get('index', 0)))
        return w.snapshot()


@app.get('/api/site')
def site(request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        return w.site_view()


@app.post('/api/site/refresh')
def refresh_site(request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.refresh_sources(force=True)
        return w.site_view()


@app.get('/api/site/value')
def value(key: str, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        return w.value_details(key)


@app.get('/api/site/region')
def region(request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        return w.region_geometry()


@app.get('/api/site/json')
def site_json(request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        data = ws.json.dumps(w.site, ensure_ascii=False, indent=2)
    return Response(data, media_type='application/json',
                    headers={'Content-Disposition': 'attachment; filename="site-conditions.json"'})


@app.post('/api/deliveries')
def save_delivery(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.save_delivery(body)
        return w.snapshot()


@app.delete('/api/deliveries/{ident}')
def archive_delivery(ident: str, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        w.archive_delivery(ident)
        return w.snapshot()


@app.post('/api/export')
def export(body: dict, request: Request, response: Response):
    w = session(request, response)
    with w.lock:
        data = w.export(body)
    return Response(data, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename="FlowerMoon-Transport.xlsx"'})


@lru_cache(maxsize=384)
def _hazard_tile(z, x, y):
    image = ws.gem_hazard.overlay(z, x * 256, y * 256, 256, 256)
    buffer = io.BytesIO()
    image.save(buffer, 'PNG', optimize=True)
    return buffer.getvalue()


@app.get('/api/hazard/{z}/{x}/{y}.png', include_in_schema=False)
def hazard_tile(z: int, x: int, y: int):
    if not 0 <= z <= 12 or not 0 <= y < 2 ** z:
        raise HTTPException(404)
    try:
        data = _hazard_tile(z, x % 2 ** z, y)
    except Exception:
        raise HTTPException(503, 'Seismic layer unavailable.') from None
    return Response(data, media_type='image/png', headers={'Cache-Control': 'public, max-age=604800'})


@app.get('/api/hazard/legend')
def hazard_legend():
    bands = ws.gem_hazard.band_labels()
    return [dict(interval=interval, label=label, color='#%02x%02x%02x' % rgb)
            for (interval, label), (_, rgb) in zip(bands, ws.gem_hazard.PALETTE)]
