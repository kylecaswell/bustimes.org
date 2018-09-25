from django.test import TestCase
from ...models import Region, Operator, DataSource, Vehicle, VehicleLocation, Service
from ..commands import import_live_ziptrip


class ZipTripTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='EA')
        Operator.objects.create(id='LYNX', region_id='EA')
        Operator.objects.create(id='CBUS', region_id='EA')
        Operator.objects.create(id='GAHL', region_id='EA')
        Operator.objects.create(id='LGEN', region_id='EA')
        cls.service = Service.objects.create(line_name='7777', date='2010-01-01')
        cls.service.operator.set(['LGEN'])

        now = '2018-08-06T22:41:15+01:00'
        cls.source = DataSource.objects.create(datetime=now)
        cls.vehicle = Vehicle.objects.create(code='203', operator_id='CBUS', source=cls.source)

    def test_handle(self):
        command = import_live_ziptrip.Command()
        command.source = self.source

        item = {
            "vehicleCode": "LYNX__2_-_YJ55_BJE",
            "routeName": "7777",
            "position": {
                "latitude": 52.731614,
                "longitude": 0.385742
            },
            "reported": "2018-08-31T21:30:04+00:00",
            "received": "2018-08-31T21:30:15.8465176+00:00",
            "bearing": -24,
        }

        command.handle_item(item, self.source.datetime)

        location = VehicleLocation.objects.get()

        self.assertEquals(336, location.heading)
        self.assertNotEquals(self.vehicle, location.vehicle)
        self.assertEquals('LYNX', location.vehicle.operator_id)

        item['vehicleCode'] = 'LAS_203'
        # Although a vehicle called '203' exists, it belongs to a different operator, so a new one should be created
        command.handle_item(item, self.source.datetime)
        location = VehicleLocation.objects.last()
        self.assertEquals('GAHL', location.vehicle.operator_id)
        self.assertNotEquals(self.vehicle, location.vehicle)
        self.assertEquals(self.service, location.service)

        self.assertEquals(3, Vehicle.objects.count())