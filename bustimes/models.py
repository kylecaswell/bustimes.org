import re
import yaml
import time
from urllib.parse import urlencode, quote
from autoslug import AutoSlugField
from django.db.models import Q
from django.contrib.gis.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.fields import DateRangeField
from django.core.cache import cache
from django.urls import reverse
from multigtfs.models import Feed


TIMING_STATUS_CHOICES = (
    ('PPT', 'Principal point'),
    ('TIP', 'Time info point'),
    ('PTP', 'Principal and time info point'),
    ('OTH', 'Other bus stop'),
)
SERVICE_ORDER_REGEX = re.compile(r'(\D*)(\d*)(\D*)')


class ValidateOnSaveMixin:
    """https://www.xormedia.com/django-model-validation-on-save/"""
    def save(self, force_insert=False, force_update=False, **kwargs):
        if not (force_insert or force_update):
            self.full_clean()
        super().save(force_insert, force_update, **kwargs)


class Operator(ValidateOnSaveMixin, models.Model):
    """An entity that operates public transport services"""

    code = models.CharField(max_length=10, unique=True)  # e.g. 'YCST'
    name = models.CharField(max_length=100, db_index=True)
    aka = models.CharField(max_length=100, blank=True)
    slug = AutoSlugField(populate_from=str, unique=True, editable=True)
    vehicle_mode = models.CharField(max_length=48, blank=True)
    parent = models.CharField(max_length=48, blank=True)
    region = models.ForeignKey('busstops.Region', models.CASCADE)

    address = models.CharField(max_length=128, blank=True)
    url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=128, blank=True)
    twitter = models.CharField(max_length=255, blank=True)

    notes = models.ManyToManyField('Note', blank=True)
    licences = models.ManyToManyField('vosa.Licence', blank=True)
    payment_methods = models.ManyToManyField('PaymentMethod', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta():
        ordering = ('name',)

    def __str__(self):
        return str(self.name or self.id)

    national_expresses = {
        'Hotel Hoppa': '24233768',
        'National Express Airport': '24233764',
        'National Express': '21039402',
    }
    national_expresses['National Express Shuttle'] = national_expresses['National Express']
    national_expresses['Woking RailAir'] = national_expresses['National Express Airport']

    def is_national_express(self):
        return self.name in self.national_expresses

    def get_national_express_url(self):
        return (
            'https://clkuk.pvnsolutions.com/brand/contactsnetwork/click?p=230590&a=3022528&g='
            + {
                **self.national_expresses,
                'Xplore Dundee': self.national_expresses['National Express Airport']
            }[self.name]
        )

    def get_absolute_url(self):
        return reverse('operator_detail', args=(self.slug or self.id,))

    def mode(self):
        return self.vehicle_mode

    def get_a_mode(self):
        """Return the the name of the operator's vehicle mode,
        with the correct indefinite article
        depending on whether it begins with a vowel.

        'Airline' becomes 'An airline', 'Bus' becomes 'A bus'.
        """
        mode = str(self.vehicle_mode).lower()
        if not mode or mode[0].lower() in 'aeiou':
            return 'An ' + mode  # 'An airline' or 'An '
        return 'A ' + mode  # 'A hovercraft'


class OperatorCode(models.Model):
    operator = models.ForeignKey(Operator, models.CASCADE)
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    code = models.CharField(max_length=100, db_index=True)

    class Meta:
        unique_together = ('operator', 'code', 'source')

    def __str__(self):
        return self.code


class StopUsage(models.Model):
    """A link between a StopPoint and a Service,
    with an order placing it in a direction (e.g. the first outbound stop)"""
    service = models.ForeignKey('Service', models.CASCADE)
    stop = models.ForeignKey('busstops.StopPoint', models.CASCADE)
    direction = models.CharField(max_length=8)
    order = models.PositiveIntegerField()
    timing_status = models.CharField(max_length=3,
                                     choices=TIMING_STATUS_CHOICES)

    class Meta():
        ordering = ('direction', 'order')

    def is_minor(self):
        return self.timing_status == 'OTH' or self.timing_status == 'TIP'


class Service(models.Model):
    """A bus service"""
    service_code = models.CharField(max_length=24)
    line_name = models.CharField(max_length=64, blank=True)
    line_brand = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True, db_index=True)
    outbound_description = models.CharField(max_length=255, blank=True)
    inbound_description = models.CharField(max_length=255, blank=True)
    slug = AutoSlugField(populate_from=str, editable=True, unique=True)
    mode = models.CharField(max_length=11)
    operator = models.ManyToManyField('bustimes.Operator', blank=True)
    region = models.ForeignKey('busstops.Region', models.CASCADE, null=True)
    stops = models.ManyToManyField('busstops.StopPoint', editable=False,
                                   through='bustimes.StopUsage')
    date = models.DateField()
    current = models.BooleanField(default=True, db_index=True)
    show_timetable = models.BooleanField(default=False)
    timetable_wrong = models.BooleanField(default=False)
    geometry = models.MultiLineStringField(null=True, editable=False)

    source = models.ForeignKey('busstops.DataSource', models.SET_NULL, null=True, blank=True)
    tracking = models.NullBooleanField()
    payment_methods = models.ManyToManyField('PaymentMethod', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    notes = models.ManyToManyField('Note', blank=True)

    class Meta():
        unique_together = ('service_code', 'source')

    def __str__(self):
        line_name = self.line_name
        description = None
        if hasattr(self, 'direction') and hasattr(self, f'{self.direction}_description'):
            description = getattr(self, f'{self.direction}_description')
        if not description or description.lower() == self.direction:
            description = self.description
        if description == line_name:
            description = None
        elif ' ' in line_name and line_name in description:
            line_name = None
        if line_name or self.line_brand or description:
            parts = (line_name, self.line_brand, description)
            return ' - '.join(part for part in parts if part)
        return self.service_code

    def yaml(self):
        return yaml.dump({
            self.pk: {
                'line_name': self.line_name,
                'line_brand': self.line_brand,
                'description': self.description,
                'outbound_description': self.outbound_description,
                'inbound_description': self.inbound_description,
                'current': self.current,
                'show_timetable': self.show_timetable,
            }
        })

    def get_line_name_and_brand(self):
        if self.line_brand:
            return f'{self.line_name} - {self.line_brand}'
        return self.line_name

    def has_long_line_name(self):
        "Is this service's line_name more than 4 characters long?"
        return len(self.line_name) > 4

    def get_a_mode(self):
        if self.mode and self.mode[0].lower() in 'aeiou':
            return 'An %s' % self.mode  # 'An underground service'
        return 'A %s' % self.mode  # 'A bus service' or 'A service'

    def get_absolute_url(self):
        return reverse('service_detail', args=(self.slug,))

    def get_order(self):
        groups = SERVICE_ORDER_REGEX.match(self.line_name).groups()
        return (groups[0], int(groups[1]) if groups[1] else 0, groups[2])

    @staticmethod
    def get_operator_number(code):
        if code in {'MEGA', 'MBGD'}:
            return '11'
        if code in {'NATX', 'NXSH', 'NXAP'}:
            return '12'
        return {
            'BHAT': '41',
            'ESYB': '53',
            'WAIR': '20',
            'TVSN': '18'
        }.get(code)

    def get_tfl_url(self):
        return f'https://tfl.gov.uk/bus/timetable/{self.line_name}/'

    def get_trapeze_link(self, date):
        if self.source.name == 'Y':
            domain = 'yorkshiretravel.net'
            name = 'Yorkshire Travel'
        else:
            domain = 'travelinescotland.com'
            name = 'Traveline Scotland'
        if date:
            date = int(time.mktime(date.timetuple()) * 1000)
        else:
            date = ''
        query = (
            ('timetableId', self.service_code),
            ('direction', 'OUTBOUND'),
            ('queryDate', date),
            ('queryTime', date)
        )
        return f'http://www.{domain}/lts/#/timetables?{urlencode(query)}', name

    def is_megabus(self):
        return (self.line_name in {'FALCON', 'Oxford Tube'}
                or self.pk in {'bed_1-X5-Z-y08', 'set_6-M2-_-y08', 'YWAX062', 'FSAG010', 'FSAM009', 'FSAG009',
                               'EDAO900', 'EDAAIR0', 'YSBX010', 'ABAX010', 'ABAO010'}
                or any(o.pk in {'MEGA', 'MBGD', 'SCMG'} for o in self.operator.all()))

    def get_megabus_url(self):
        # Using a tuple of tuples, instead of a dict, because the order is important for tests
        query = (
            ('mid', 2678),
            ('id', 242611),
            ('clickref', 'links'),
            ('clickref2', self.service_code),
            ('p', 'https://uk.megabus.com'),
        )
        return 'https://www.awin1.com/awclick.php?' + urlencode(query)

    def get_traveline_links(self, date=None):
        if self.source_id and self.source.name in ('Y', 'S'):
            yield self.get_trapeze_link(date)
            return

        if self.region_id == 'W':
            for service_code in self.servicecode_set.filter(scheme='Traveline Cymru'):
                query = (
                    ('routeNum', self.line_name),
                    ('direction_id', 0),
                    ('timetable_key', service_code.code)
                )
                url = 'https://www.traveline.cymru/timetables/?' + urlencode(query)
                yield (url, 'Traveline Cymru')
            return

        base_url = 'http://www.travelinesoutheast.org.uk/se'
        base_query = [('command', 'direct'), ('outputFormat', 0)]

        if self.region_id == 'GB':
            parts = self.service_code.split('_')
            operator_number = self.get_operator_number(parts[1])
            if operator_number is not None:
                query = [('line', operator_number + parts[0][:3].zfill(3)),
                         ('sup', parts[0][3:]),
                         ('net', 'nrc'),
                         ('project', 'y08')]
                yield (
                    f'{base_url}/XSLT_TTB_REQUEST?{urlencode(query + base_query)}',
                    'Traveline'
                )

        elif '-' in self.service_code and '_' in self.service_code[2:4]:
            if self.servicecode_set.filter(scheme='TfL').exists():
                yield (self.get_tfl_url(), 'Transport for London')
                return

            if self.service_code.startswith('tfl_'):
                return

            try:
                for route in self.route_set.all():
                    parts = route.code.split('-')
                    net, line = parts[0].split('_')
                    line_ver = parts[4][:-4]
                    line = line.zfill(2) + parts[1].zfill(3)

                    query = [('line', line),
                             ('lineVer', line_ver),
                             ('net', net),
                             ('project', parts[3])]
                    if parts[2] != '_':
                        query.append(('sup', parts[2]))

                    yield (
                        f'{base_url}/XSLT_TTB_REQUEST?{urlencode(query + base_query)}',
                        'Traveline'
                    )
            except ValueError:
                pass

    def get_linked_services_cache_key(self):
        return f'{quote(self.service_code)}linked_services{self.date}'

    def get_similar_services_cache_key(self):
        return f'{quote(self.service_code)}similar_services{self.date}'

    def get_linked_services(self):
        key = self.get_linked_services_cache_key()
        services = cache.get(key)
        if services is None:
            services = list(Service.objects.filter(
                Q(link_from__to_service=self, link_from__how='parallel')
                | Q(link_to__from_service=self, link_to__how='parallel')
            ).order_by().defer('geometry'))
            cache.set(key, services)
        return services

    def get_similar_services(self):
        key = self.get_similar_services_cache_key()
        services = cache.get(key)
        if services is None:
            q = Q(link_from__to_service=self) | Q(link_to__from_service=self)
            if self.description and self.line_name:
                q |= Q(description=self.description)
                q |= Q(line_name=self.line_name, operator__in=self.operator.all())
            services = Service.objects.filter(~Q(pk=self.pk), q, current=True).order_by().defer('geometry')
            services = sorted(services.distinct().prefetch_related('operator'), key=Service.get_order)
            cache.set(key, services)
        return services


class ServiceCode(models.Model):
    service = models.ForeignKey(Service, models.CASCADE)
    scheme = models.CharField(max_length=255)
    code = models.CharField(max_length=255)

    class Meta():
        unique_together = ('service', 'scheme', 'code')

    def __str__(self):
        return '{} {}'.format(self.scheme, self.code)

    def get_routes(self):
        feed = Feed.objects.filter(name=self.scheme.split()[0]).latest('created')
        return feed.route_set.filter(feed=feed, route_id=self.code)


class ServiceLink(models.Model):
    from_service = models.ForeignKey(Service, models.CASCADE, 'link_from')
    to_service = models.ForeignKey(Service, models.CASCADE, 'link_to')
    how = models.CharField(max_length=10, choices=(
        ('parallel', 'Combine timetables'),
        ('also', 'Just list'),
    ))

    def get_absolute_url(self):
        return self.from_service.get_absolute_url()


class PaymentMethod(models.Model):
    name = models.CharField(max_length=48)
    url = models.URLField(blank=True)

    def __str__(self):
        return self.name


class Contact(models.Model):
    from_name = models.CharField(max_length=255)
    from_email = models.EmailField()
    message = models.TextField()
    spam_score = models.PositiveIntegerField()
    ip_address = models.GenericIPAddressField()
    referrer = models.URLField(blank=True)


class Route(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    code = models.CharField(max_length=255)
    line_brand = models.CharField(max_length=255, blank=True)
    line_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    dates = DateRangeField(null=True, blank=True)
    service = models.ForeignKey('Service', models.CASCADE)

    class Meta:
        unique_together = ('source', 'code')
        index_together = (
            ('start_date', 'end_date'),
        )

    def __str__(self):
        return ' – '.join(part for part in (self.line_name, self.line_brand, self.description) if part)


class Calendar(models.Model):
    mon = models.BooleanField()
    tue = models.BooleanField()
    wed = models.BooleanField()
    thu = models.BooleanField()
    fri = models.BooleanField()
    sat = models.BooleanField()
    sun = models.BooleanField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    dates = DateRangeField(null=True)

    class Meta:
        index_together = (
            ('start_date', 'end_date'),
        )

    def __str__(self):
        return f'{self.start_date} to {self.end_date}'


class CalendarDate(models.Model):
    calendar = models.ForeignKey('Calendar', models.CASCADE)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    dates = DateRangeField(null=True)
    operation = models.BooleanField(db_index=True)
    special = models.BooleanField(default=False, db_index=True)


class Note(models.Model):
    code = models.CharField(max_length=16)
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text

    def get_absolute_url(self):
        return self.trip_set.first().route.service.get_absolute_url()


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    destination = models.ForeignKey('busstops.StopPoint', models.CASCADE)
    calendar = models.ForeignKey('Calendar', models.CASCADE)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    start = models.DurationField()
    end = models.DurationField()

    class Meta:
        index_together = (
            ('route', 'start', 'end'),
        )

    def __cmp__(a, b):
        """Compare two journeys"""
        if a.sequence is not None and a.sequence is not None:
            a_time = a.sequence
            b_time = b.sequence
        else:
            a_time = a.start
            b_time = b.start
            a_times = a.stoptime_set.all()
            b_times = b.stoptime_set.all()
            if a_times[0].stop_code != b_times[0].stop_code:
                if a.destination_id == b.destination_id:
                    a_time = a.end
                    b_time = b.end
                else:
                    times = {stop_time.stop_code: stop_time.arrival or stop_time.departure for stop_time in a_times}
                    for stop_time in b_times:
                        if stop_time.stop_code in times:
                            a_time = times[stop_time.stop_code]
                            b_time = stop_time.arrival or stop_time.departure
                            break
                        # if cell.arrival_time >= y.departure_time:
                        #     if times[cell.stopusage.stop.atco_code] >= x.departure_time:
                        #         x_time = times[cell.stopusage.stop.atco_code]
                        #         y_time = cell.arrival_time
                        # break
        if a_time > b_time:
            return 1
        if a_time < b_time:
            return -1
        return 0

    def __repr__(self):
        return str(self.start)


class StopTime(models.Model):
    trip = models.ForeignKey(Trip, models.CASCADE)
    stop_code = models.CharField(max_length=255)
    stop = models.ForeignKey('busstops.StopPoint', models.SET_NULL, null=True, blank=True)
    arrival = models.DurationField()
    departure = models.DurationField()
    sequence = models.PositiveSmallIntegerField()
    timing_status = models.CharField(max_length=3, blank=True)
    activity = models.CharField(max_length=16, blank=True)

    class Meta:
        ordering = ('sequence',)
        index_together = (
            ('stop', 'departure'),
        )
