"""Bounded truck-route segmentation for public-server distance limits.

Every metre and travel time comes from Valhalla. Automatic intermediate points
constrain the route; no straight-line distance is substituted for a missing leg.
"""
from copy import deepcopy
from math import radians, sin, cos, atan2, sqrt


def separation(a, b):
    p, q = radians(a[1]), radians(b[1])
    h = sin((q-p)/2)**2 + cos(p)*cos(q)*sin(radians(b[0]-a[0])/2)**2
    return 6371000 * 2 * atan2(sqrt(min(1, h)), sqrt(max(0, 1-h)))


def midpoint(a, b):
    # Unwrap longitude so a route over the date line is not sent via Greenwich.
    delta = (b['lon']-a['lon']+180) % 360-180
    return dict(lat=(a['lat']+b['lat'])/2,
                lon=(a['lon']+delta/2+180) % 360-180,
                type='break', search_cutoff=5000)


def segmented_route(payload, fetch, parse):
    """At most four successful legs / seven follow-up calls. Fail atomically."""
    calls = 0
    legs = []
    requests = []
    automatic = []

    def leg(a, b, depth=0):
        nonlocal calls
        if calls >= 7 or len(legs) >= 4:
            raise ValueError('Route exceeds the automatic segmentation limit. Add closer waypoints or configure a Valhalla server with a higher distance limit.')
        body = deepcopy(payload)
        body.update(locations=[dict(a, type='break'), dict(b, type='break')], alternates=0)
        calls += 1
        try:
            result = parse(fetch(body))[0]
        except ValueError as error:
            if getattr(error, 'provider_code', None) != 'DistanceExceeded' or depth >= 2:
                raise
            mid = midpoint(a, b)
            automatic.append(dict(mid))
            leg(a, mid, depth+1)
            end = legs[-1]['geometry']['coordinates'][-1]
            leg(dict(mid, lon=end[0], lat=end[1]), b, depth+1)
            return
        if legs:
            end = legs[-1]['geometry']['coordinates'][-1]
            start = result['geometry']['coordinates'][0]
            if separation(end, start) > 1:
                raise ValueError('The route stages do not connect on the same road. Select a road junction as an explicit waypoint and recalculate.')
        legs.append(result)
        requests.append(body)

    points = payload['locations']
    if len(points) == 2:
        mid = midpoint(*points)
        automatic.append(dict(mid))
        leg(points[0], mid, 1)
        end = legs[-1]['geometry']['coordinates'][-1]
        leg(dict(mid, lon=end[0], lat=end[1]), points[1], 1)
    else:
        if len(points) > 5:
            raise ValueError('Too many stages for automatic routing. Use a server with a higher distance limit.')
        for a, b in zip(points, points[1:]):
            if legs:
                end = legs[-1]['geometry']['coordinates'][-1]
                a = dict(a, lon=end[0], lat=end[1])
            leg(a, b)
    geometry = [p for item in legs for p in item['geometry']['coordinates']]
    merged = dict(name='Option 1 · staged',
                  distance_km=sum(r['distance_km'] for r in legs),
                  hours=sum(r['hours'] for r in legs),
                  geometry=dict(type='LineString', coordinates=geometry),
                  ferryDetected=any(r['ferryDetected'] for r in legs),
                  crossings=[c for r in legs for c in r.get('crossings', [])],
                  routeSegments=[dict(request=req, distance_km=r['distance_km'], hours=r['hours']) for req, r in zip(requests, legs)],
                  automaticWaypoints=automatic,
                  routingNote=f'{len(legs)} Valhalla truck stages to respect the server distance limit. '
                  + ('Automatic intermediate points constrain this route; it may not be the fastest overall. ' if automatic else 'Uses your via points. ')
                  + 'Review the route with the carrier.')
    if all('road_distance_km' in r for r in legs):
        merged['road_distance_km'] = sum(r['road_distance_km'] for r in legs)
        merged['crossing_distance_km'] = sum(r['crossing_distance_km'] for r in legs)
    return [merged]


def route_description(route):
    parts = []
    if route.get('crossings'):
        if 'road_distance_km' in route:
            parts.append(f"Road / other: {route['road_distance_km']:,.1f} km · Ferry: {route['crossing_distance_km']:,.1f} km.")
        names = list(dict.fromkeys(c['name'] for c in route['crossings']))
        parts.append('Crossing: ' + '; '.join(names) + '.')
        parts.append('Time is a route estimate; confirm sailing times, check-in, vehicle acceptance and crossing fares with the operator. Per-km costing uses total route distance; add crossing fares separately.')
    if route.get('routingNote'):
        parts.append(route['routingNote'])
    return ' '.join(parts)
