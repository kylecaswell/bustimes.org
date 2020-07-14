from busstops.models import Service
from .import_nx import sleep, RequestException, Command as NatExpCommand


class Command(NatExpCommand):
    source_name = 'Aircoach'
    operators = ['663']
    url = 'https://tracker.aircoach.ie/api/eta/routes/{}/{}'
    sleep = 10
