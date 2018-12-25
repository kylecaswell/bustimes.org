from freezegun import freeze_time
from django.test import TestCase
from django.contrib.gis.geos import Point
from busstops.models import DataSource
from .models import Vehicle, VehicleJourney, VehicleLocation
# from ..commands import import_bushub


class VehiclesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        datetime = '2018-12-25 19:47+00:00'
        source = DataSource.objects.create(name='HP', datetime=datetime)
        cls.vehicle_1 = Vehicle.objects.create(fleet_number=1, reg='FD54JYA')
        cls.vehicle_2 = Vehicle.objects.create(fleet_number=50, reg='UWW2X')
        journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=datetime, source=source)
        VehicleLocation.objects.create(datetime=datetime, latlong=Point(0, 51), journey=journey, current=True)

    def test_vehicles_json(self):
        with self.assertNumQueries(2):
            response = self.client.get('/vehicles.json?ymax=52&xmax=2&ymin=51&xmin=1')
            self.assertEqual(200, response.status_code)
            self.assertEqual({'type': 'FeatureCollection', 'features': []}, response.json())
            self.assertIsNone(response.get('last-modified'))

        with self.assertNumQueries(2):
            response = self.client.get('/vehicles.json')
            self.assertEqual(response.json()['features'][0]['properties']['vehicle']['reg'], 'FD54 JYA')
            self.assertEqual(response.get('last-modified'), 'Tue, 25 Dec 2018 19:47:00 GMT')

    def test_location_json(self):
        location = VehicleLocation.objects.get()
        location.journey.vehicle = self.vehicle_2
        json = location.get_json()
        self.assertEqual(json['properties']['vehicle']['reg'], 'UWW 2X')

    @freeze_time('4 July 1940')
    def test_vehicle_detail(self):
        vehicle = Vehicle.objects.get(fleet_number='50')
        response = self.client.get(vehicle.get_absolute_url() + '?date=poo poo pants')
        self.assertEqual('1940-07-04', str(response.context['date']))
        self.assertContains(response, 'Sorry, nothing found for')
