"""
Usage:

    ./manage.py import_operators < NOC_db.csv
"""

from django.utils import timezone
from ..import_from_csv import ImportFromCSVCommand
from ...models import Operator, OperatorCode, DataSource


class Command(ImportFromCSVCommand):
    removed_operator_ids = {
        'TVSR', 'HBSY', 'OWML', 'POTD', 'ANUM', 'BCOA', 'EAST', 'AW', 'ACAH', 'PFCL',
        'EABU',  # EasyBus - duplicate of ESYB
        'ANGL',  # Anglian Bus - merged into Konectbus (KCTB)
    }
    code_sources = {
        'NOCCODE': 'National Operator Codes',
        'Licence': 'Licence',
        'LO': 'L',
        'SW': 'SW',
        'WM': 'WM',
        'WA': 'W',
        'YO': 'Y',
        'NW': 'NW',
        'NE': 'NE',
        'SC': 'S',
        'SE': 'SE',
        'EA': 'EA',
        'EM': 'EM',
    }

    @staticmethod
    def get_region_id(region_id):
        if region_id in {'ADMIN', 'Admin', 'Taxi', ''}:
            return 'GB'
        elif region_id in {'SC', 'YO', 'WA', 'LO'}:
            return region_id[0]

        return region_id

    @staticmethod
    def is_rubbish_name(name):
        """Given an OperatorPublicName, return True if it should be
        ignored in favour of the RefNm or OpNm fields
        """
        return (
            name in {'First', 'Arriva', 'Stagecoach', 'Oakwood Travel', 'Arriva North West'} or
            name.startswith('inc.') or
            name.startswith('formerly') or
            name.isupper()
        )

    @classmethod
    def get_name(cls, row):
        """Given a row dictionary, returns the best-seeming name string"""
        if cls.is_rubbish_name(row['OperatorPublicName']):
            if row['RefNm'] != '':
                return row['RefNm']
            return row['OpNm']
        if row['OperatorPublicName'] != '':
            return row['OperatorPublicName']
        return row['OpNm']

    def handle_row(self, row):
        """Given a CSV row (a list), returns an Operator object"""

        operator_id = row['NOCCODE'].replace('=', '')
        # Avoid duplicates, for:
        #  - operators with multiple National Operator Codes
        #    (Travelsure, Yorkshire Tiger, Owens, Horseless Carriage Services etc)
        #  - operators with multiple different rows for the same NOC (First Manchester)
        #  - GB operators with no services who clash with Ireland operator names (Eastons Coaches, Aircoach)
        if (
                operator_id in self.removed_operator_ids
                or operator_id == 'FMAN' and row['Duplicate'] != 'OK'
        ):
            return

        name = self.get_name(row).replace('\'', '\u2019')  # Fancy apostrophe

        mode = row['Mode'].lower()
        if mode == 'airline':
            return
        if mode == 'ct operator':
            mode = 'community transport'
        elif mode == 'drt':
            mode = 'demand responsive transport'

        defaults = {
            'name': name.strip(),
            'vehicle_mode': mode,
            'region_id': self.get_region_id(row['TLRegOwn']),
        }

        operator = Operator.objects.update_or_create(
            id=operator_id,
            defaults=defaults
        )[0]
        for key in self.code_sources:
            if row[key]:
                OperatorCode.objects.update_or_create(code=row[key].replace('=', ''), source=self.code_sources[key],
                                                      defaults={'operator': operator})

    def handle(self, *args, **options):
        Operator.objects.filter(id__in=self.removed_operator_ids).delete()
        for key in self.code_sources:
            self.code_sources[key] = DataSource.objects.get_or_create(name=self.code_sources[key], defaults={
                'datetime': timezone.now()
            })[0]
        return super(Command, self).handle(*args, **options)
