from django.test import TestCase
from .models import Region, AdminArea, District, Locality, StopPoint


class RegionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create some regions
        cls.midlands = Region.objects.create(pk='NM', name='North Midlands')
        cls.east = Region.objects.create(pk='ME', name='Middle East')
        cls.ireland = Region.objects.create(pk='IE', name='Ireland')

    def test_string(self):
        self.assertEqual(str(self.midlands), 'North Midlands')

    def test_the(self):
        "Regions with certain names should have 'the' prepended, and others shouldn't."
        self.assertEqual(self.midlands.the(), 'the North Midlands')
        self.assertEqual(self.east.the(), 'the Middle East')
        self.assertEqual(self.ireland.the(), 'Ireland')

    def test_get_absolute_url(self):
        self.assertEqual(self.midlands.get_absolute_url(), '/regions/NM')


class LocalityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.midlands = Region.objects.create(pk='NM', name='North Midlands')
        cls.dorset = AdminArea.objects.create(pk='4', atco_code=2, region=cls.midlands, name='Dorset')

        cls.north_yorkshire = District.objects.create(pk='2', admin_area=cls.dorset, name='North Yorkshire')

        cls.brinton = Locality.objects.create(pk='1', admin_area=cls.dorset, name='Brinton')
        cls.york = Locality.objects.create(pk='2', admin_area=cls.dorset, name='York', qualifier_name='York')

    def test_get_qualified_name(self):
        self.assertEqual(self.brinton.get_qualified_name(), 'Brinton')
        self.assertEqual(self.york.get_qualified_name(), 'York, York')

    def test_string(self):
        self.assertEqual(str(self.brinton), 'Brinton')
        self.assertEqual(str(self.york), 'York')

        self.assertEqual(str(self.brinton.admin_area), 'Dorset')


class StopPointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiff_airport_locality = Locality(name='Cardiff Airport')
        cls.cardiff_airport_stop = StopPoint(common_name='Airport', locality=cls.cardiff_airport_locality)
        cls.ballyblack_church = StopPoint.objects.create(atco_code='700000002498', locality_centre=False, active=True,
                                                         common_name='Ballyblack Church', town='Ballyblack')

    def test_get_qualified_name(self):
        self.assertEqual('Ballyblack Church', self.ballyblack_church.get_qualified_name())
        self.ballyblack_church.common_name = 'Methodist Church'
        self.assertEqual('Ballyblack Methodist Church', self.ballyblack_church.get_qualified_name())

        self.assertEqual('Cardiff Airport', self.cardiff_airport_stop.get_qualified_name())
        self.cardiff_airport_stop.indicator = 'Stop M'
        self.assertEqual('Cardiff Airport (Stop M)', self.cardiff_airport_stop.get_qualified_name())
