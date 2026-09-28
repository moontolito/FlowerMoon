import io,json,unittest
from copy import deepcopy
from urllib.error import HTTPError
from unittest.mock import patch
import routing
from domain import route_request,parse_response
from route_segments import midpoint


def response(body, ferry=False):
    a,b=body['locations']
    return {'code':'Ok','routes':[{'distance':100000,'duration':7200,
        'geometry':{'type':'LineString','coordinates':[[a['lon'],a['lat']],[b['lon'],b['lat']]]},
        'legs':[{'steps':[{'mode':'driving','distance':80000 if ferry else 100000,'duration':5000},
            *([{'mode':'ferry','name':'Test crossing','distance':20000,'duration':2200}] if ferry else [])]}]}]}


class CrossingRoutes(unittest.TestCase):
    def setUp(self):
        self.payload=route_request({'lat':48,'lon':26},{'lat':52,'lon':-1},
            dict(length=18,width=3,height=4.2,weight=25,axle_count=6,axle_load=9))

    def test_distance_limit_stages_preserve_truck_and_input(self):
        original=deepcopy(self.payload);calls=[]
        def fetch(url,body):
            calls.append(deepcopy(body))
            if len(calls)==1:raise routing.RoutingServiceError('limit','DistanceExceeded')
            return response(body,len(calls)==3)
        with patch('routing.request',side_effect=fetch):
            result=routing.route('https://example.org',self.payload)[0]
        self.assertEqual(len(calls),3)
        self.assertEqual(self.payload,original)
        for body in calls:
            self.assertEqual(body['costing'],'truck')
            self.assertEqual(body['costing_options'],original['costing_options'])
        self.assertEqual(result['distance_km'],200)
        self.assertEqual(result['road_distance_km'],180)
        self.assertEqual(result['crossing_distance_km'],20)
        self.assertEqual(result['hours'],4)
        self.assertTrue(result['ferryDetected'])
        self.assertEqual(len(result['routeSegments']),2)
        self.assertEqual(len(result['automaticWaypoints']),1)

    def test_short_route_keeps_alternatives_and_avoids_extra_requests(self):
        with patch('routing.request',return_value=response(self.payload)) as fetch:
            result=routing.route('https://example.org',self.payload)
        fetch.assert_called_once()
        self.assertNotIn('routeSegments',result[0])

    def test_failed_second_stage_never_returns_partial_distance(self):
        calls=[]
        def fetch(url,body):
            calls.append(body)
            if len(calls)==1:raise routing.RoutingServiceError('limit','DistanceExceeded')
            if len(calls)==3:raise routing.RoutingServiceError('No truck route','NoRoute')
            return response(body)
        with patch('routing.request',side_effect=fetch),self.assertRaisesRegex(ValueError,'No truck route'):
            routing.route('https://example.org',self.payload)
        self.assertEqual(len(calls),3)

    def test_no_split_for_no_route_or_rate_limit(self):
        for code in ['NoRoute','TooManyRequests']:
            with patch('routing.request',side_effect=routing.RoutingServiceError(code,code)) as fetch,self.assertRaises(ValueError):
                routing.route('https://example.org',self.payload)
            fetch.assert_called_once()

    def test_disconnected_stages_not_joined_by_invented_line(self):
        calls=[]
        def fetch(url,body):
            calls.append(body)
            if len(calls)==1:raise routing.RoutingServiceError('limit','DistanceExceeded')
            r=response(body)
            if len(calls)==3:r['routes'][0]['geometry']['coordinates'][0][0]+=1
            return r
        with patch('routing.request',side_effect=fetch),self.assertRaisesRegex(ValueError,'do not connect'):
            routing.route('https://example.org',self.payload)

    def test_persistent_distance_limit_is_bounded(self):
        with patch('routing.request',side_effect=routing.RoutingServiceError('limit','DistanceExceeded')) as fetch,self.assertRaises(ValueError):
            routing.route('https://example.org',self.payload)
        self.assertLessEqual(fetch.call_count,8)

    def test_existing_waypoint_is_preserved(self):
        self.payload['locations'].insert(1,dict(lat=49,lon=10,type='via'))
        calls=[]
        def fetch(url,body):
            calls.append(body)
            if len(calls)==1:raise routing.RoutingServiceError('limit','DistanceExceeded')
            return response(body)
        with patch('routing.request',side_effect=fetch):
            r=routing.route('https://example.org',self.payload)[0]
        self.assertEqual(r['automaticWaypoints'],[])
        self.assertEqual(calls[1]['locations'][-1]['lon'],10)

    def test_provider_json_is_retained_and_html_is_not_shown(self):
        for body,code in [(b'{"code":"DistanceExceeded","message":"Path distance exceeds the max distance limit."}','DistanceExceeded'),(b'<html>gateway</html>',None)]:
            error=HTTPError('https://example.org',400,'Bad request',{},io.BytesIO(body))
            with patch('routing.urlopen',side_effect=error),patch('routing.time.sleep'),self.assertRaises(routing.RoutingServiceError) as context:
                routing.request('https://example.org',self.payload)
            self.assertEqual(context.exception.provider_code,code)
            self.assertNotIn('<html>',str(context.exception))

    def test_missing_steps_do_not_fabricate_road_distance(self):
        data=response(self.payload);data['routes'][0].pop('legs')
        self.assertNotIn('road_distance_km',parse_response(data)[0])

    def test_midpoint_crosses_date_line(self):
        point=midpoint(dict(lat=0,lon=179),dict(lat=0,lon=-179))
        self.assertEqual(abs(point['lon']),180)


if __name__=='__main__':unittest.main()
