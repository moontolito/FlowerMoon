# Long-distance truck routes and ferry crossings — 2026-09-27

## Observed problem

The configured public Valhalla server returned HTTP 400 / `DistanceExceeded`
for Botosani (47.7593182, 26.6256076) to Combe, England
(51.8483743, -1.4094779). Requesting a single route with ferries preferred
did not resolve the distance limit. The old client hid the provider's message;
the planner could replace the error with an unrelated address-selection hint.

## Change

- Keep normal routing and alternatives for requests that succeed.
- Only on the provider's distance-limit response, request a bounded series of
  truck stages: at most four completed stages / seven follow-up requests.
- Use existing via points when supplied. Otherwise propose an intermediate
  coordinate, searching for a routable location within 5 km. Longitude wraps
  across the date line. Every distance, duration and route shape comes from
  Valhalla, never from the straight line between points.
- Preserve all truck dimensions, axle/weight values and restriction flags.
  Ferries are explicitly permitted with Valhalla's neutral `use_ferry=0.5`.
- Use the snapped end of the preceding stage for the next departure. Reject
  stage geometries that fail to connect within one metre (rounding tolerance).
  Do not present a total unless every stage succeeded. Stop on rate limits,
  disconnected networks or no truck route instead of switching to car costing.
- Retain stage requests and automatic intermediate points in route provenance.
  Explain that intermediate points constrain the route and may affect optimality.
- Retain named OSRM `ferry` steps and their provider distances/times. Display
  total route distance and detected ferry distance. The remainder is labelled
  "Road / other": OSRM driving-mode steps do not reliably distinguish a rail
  vehicle shuttle, so no unsupported claim of complete modal coverage is made.
- Use "Travel estimate" instead of "Driving hours" for the map-first planner
  and Excel Routes sheet. Keep crossing/method notes in Excel and distance details.
- Surface provider errors and clear old crossing text when inputs change.

## Scope and limits

This supports truck-accessible ferry connections present in Valhalla/OSM. It is
not a global cargo-shipping network or an operator timetable/booking service.
An automatic intermediate point may not work across oceans or disconnected
networks; then an explicit road waypoint or a server with higher limits is needed.
Carrier acceptance, cargo dimensions, permits, sailing/check-in times and fares
still require confirmation. A ferry is not automatically a marine exposure or
a destination corrosivity category; inland ferries remain possible.

Existing per-km costing continues to use total route kilometres. Crossing fares
must be added separately to fixed trip costs. No fare was invented. Travel time
is the routing model's estimate, not a promised delivery time or a driver-hours plan.

## Verification

- Real end-to-end request with a 6 t, 9 m x 2.55 m x 3 m test truck:
  2,907.461125 km total; 2,865.639121 km road/other;
  41.822004 km Calais–Dover ferry; 33.6539214 h routing estimate.
- The real route used two stages, connected at the returned snapped location.
- 119 unit tests passed, including ten new cases for restrictions, stage failures,
  bounded retries, error parsing, date-line points, ferry data and user waypoints.
- Native Tkinter verification with the saved real response: route selection,
  ferry details, export provenance, 1000x700 layout, stale-result cleanup and
  error-message preservation passed. Screenshots captured from the test window.

Official method references:
- https://valhalla.github.io/valhalla/api/route/api-reference/
- https://github.com/valhalla/valhalla/blob/master/src/tyr/route_serializer_osrm.cc

Local source update only. Existing planning data, GitHub and the previously
exported testing EXE are unchanged. Restart the local app to load the new source.
