import os
import time_machine
from vcr import use_cassette
from mock import patch
from django.test import TestCase, override_settings
from busstops.models import Region, Operator
from ...models import Vehicle
from ..commands import import_tfwm


DIR = os.path.dirname(os.path.abspath(__file__))


class TfWMImportTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Region.objects.create(id='WM')
        Operator.objects.bulk_create([
            Operator(id='FSMR', region_id='WM', name='First Worcestershire'),
            Operator(id='MDCL', region_id='WM', name='Midland Classic'),
            Operator(id='SLBS', region_id='WM', name='Select Bus Services'),
        ])

    @use_cassette(os.path.join(DIR, 'vcr', 'import_tfwm.yaml'), decode_compressed_response=True)
    @time_machine.travel('2018-08-21 00:00:09')
    def test_handle(self):
        command = import_tfwm.Command()
        command.do_source()

        with override_settings(TFWM={}):
            items = command.get_items()

        with self.assertNumQueries(10):  # X12
            with patch('builtins.print') as mocked_print:
                command.handle_item(items[0])
                command.save()
        mocked_print.assert_called()

        with self.assertNumQueries(10):
            with patch('builtins.print') as mocked_print:
                command.handle_item(items[217])
                command.save()
        mocked_print.assert_called()

        with self.assertNumQueries(2):
            with patch('builtins.print') as mocked_print:
                command.handle_item(items[217])
                command.save()
        mocked_print.assert_called()

        with self.assertNumQueries(11):
            with patch('builtins.print') as mocked_print:
                command.handle_item(items[216])
                command.save()
        mocked_print.assert_called()

        self.assertEqual(3, Vehicle.objects.all().count())
