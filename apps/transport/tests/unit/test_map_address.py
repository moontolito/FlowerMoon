import unittest
from unittest.mock import patch
from urllib.parse import urlparse,parse_qs
import places

class MapAddressTests(unittest.TestCase):
    def tearDown(self):places.reverse.cache_clear()
    def test_reverse_preserves_requested_and_matched_points_and_cache(self):
        response={'features':[{'geometry':{'coordinates':[151.2101,-33.86]},'properties':{'street':'Test Street','housenumber':'10','city':'Sydney','country':'Australia'}}]}
        with patch('places.request',return_value=response) as req:
            result=places.reverse(-33.859,151.21)
            self.assertEqual(result['status'],'ready');self.assertIn('Sydney',result['label'])
            self.assertEqual(result['requestedCoordinates'],dict(lat=-33.859,lon=151.21))
            self.assertNotEqual(result['matchedCoordinates'],result['requestedCoordinates'])
            self.assertEqual(places.reverse(-33.859,151.21),result);req.assert_called_once()
            parsed=urlparse(req.call_args.args[0]);query=parse_qs(parsed.query)
            self.assertEqual(parsed.path,'/reverse');self.assertEqual(query['lang'],['en'])
            self.assertEqual(query['radius'],['1']);self.assertIn('photon',result['sourceUrl'])
    def test_no_address_and_invalid_coordinates(self):
        with patch('places.request',return_value={'features':[]}):
            self.assertEqual(places.reverse(0,0)['status'],'unavailable')
        with patch('places.request') as req:
            for lat,lon in ((91,1),(1,181),(float('nan'),1)):
                with self.assertRaises(ValueError):places.reverse(lat,lon)
            req.assert_not_called()
