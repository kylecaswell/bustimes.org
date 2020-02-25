from django.test import TestCase
from busstops.models import Region, DataSource
from .models import Operator, Service, ServiceCode
from .admin import OperatorAdmin


class OperatorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(pk='N', name='North')
        cls.chariots = Operator.objects.create(code='CHAR', region=cls.north,
                                               name='Ainsley\'s Chariots')

    def test_get_qualified_name(self):
        self.assertEqual(str(self.chariots), 'Ainsley\'s Chariots')

    def test_admin(self):
        admin = OperatorAdmin(Operator, None)
        operators = admin.get_queryset(None)
        self.assertEqual(len(operators), 1)
        self.assertEqual(admin.service_count(operators[0]), 0)
        self.assertEqual(admin.operator_codes(operators[0]), '')


class ServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(id='L', name='London')
        cls.london_service = Service.objects.create(
            service_code='tfl_8-N41-_-y05', line_name='N41',
            date='2000-1-1', region_id='L'
        )

    def test_str(self):
        self.assertEqual(str(self.london_service), 'N41')

        self.london_service.line_name = ''
        self.assertEqual(str(self.london_service), 'tfl_8-N41-_-y05')
        self.london_service.line_name = 'N41'

        service = Service(line_name='C', description='Coasthopper - Filey')
        self.assertEqual(str(service), 'C - Coasthopper - Filey')

        service.line_name = 'Coast Hopper'
        service.description = 'Coast Hopper'
        self.assertEqual(str(service), 'Coast Hopper')

        service.line_name = 'Coast Hopper'
        service.description = 'Coast Hopper – Brighton - Filey'
        self.assertEqual(str(service), 'Coast Hopper – Brighton - Filey')

    def test_get_a_mode(self):
        self.assertEqual(self.london_service.get_a_mode(), 'A ')

        self.london_service.mode = 'Underground'
        self.assertEqual(self.london_service.get_a_mode(), 'An Underground')

    def test_traveline_links(self):
        # none
        self.assertEqual([], list(self.london_service.get_traveline_links()))

        # TfL
        ServiceCode.objects.create(service=self.london_service, code='N41', scheme='TfL')
        self.assertEqual(list(self.london_service.get_traveline_links()),
                         [('https://tfl.gov.uk/bus/timetable/N41/', 'Transport for London')])

        # Yorkshire
        self.london_service.source = DataSource.objects.create(name='Y')
        self.assertEqual(
            list(self.london_service.get_traveline_links()),
            [('http://www.yorkshiretravel.net/lts/#/timetables?timetableId='
              + 'tfl_8-N41-_-y05&direction=OUTBOUND&queryDate=&queryTime=', 'Yorkshire Travel')]
        )

    def test_get_operator_number(self):
        self.assertIsNone(self.london_service.get_operator_number('MGBD'))

        self.assertEqual('11', self.london_service.get_operator_number('MEGA'))
        self.assertEqual('11', self.london_service.get_operator_number('MBGD'))

        self.assertEqual('12', self.london_service.get_operator_number('NATX'))
        self.assertEqual('12', self.london_service.get_operator_number('NXSH'))
        self.assertEqual('12', self.london_service.get_operator_number('NXAP'))

        self.assertEqual('41', self.london_service.get_operator_number('BHAT'))
        self.assertEqual('53', self.london_service.get_operator_number('ESYB'))
        self.assertEqual('20', self.london_service.get_operator_number('WAIR'))
        self.assertEqual('18', self.london_service.get_operator_number('TVSN'))
