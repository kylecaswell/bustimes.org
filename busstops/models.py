from autoslug import AutoSlugField
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.contrib.postgres.search import SearchVectorField
from django.core.cache import cache
from django.urls import reverse
from django.utils.text import slugify
from bustimes.models import Service, TIMING_STATUS_CHOICES


class Region(models.Model):
    """The largest type of geographical area"""
    id = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=48)

    class Meta():
        ordering = ('name',)

    def __str__(self):
        return self.name

    def the(self):
        """Return the name for use in a sentence,
        with the definite article prepended if appropriate"""
        if self.name[-2:] in ('ds', 'st'):
            return 'the ' + self.name
        else:
            return self.name

    def get_absolute_url(self):
        return reverse('region_detail', args=(self.id,))


class AdminArea(models.Model):
    """An administrative area within a region,
    or possibly a national transport (rail/air/ferry) network
    """
    id = models.PositiveIntegerField(primary_key=True)
    atco_code = models.PositiveIntegerField()
    name = models.CharField(max_length=48)
    short_name = models.CharField(max_length=48, blank=True)
    country = models.CharField(max_length=3, blank=True)
    region = models.ForeignKey(Region, models.CASCADE)

    class Meta():
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('adminarea_detail', args=(self.id,))


class District(models.Model):
    """A district within an administrative area.
    Note: some administrative areas *do not* have districts.
    """
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)

    class Meta():
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('district_detail', args=(self.id,))


class Locality(models.Model):
    """A locality within an administrative area,
    and possibly within a district.

    Localities may be children of other localities...
    """
    id = models.CharField(max_length=48, primary_key=True)
    name = models.CharField(max_length=48)
    # short_name?
    qualifier_name = models.CharField(max_length=48, blank=True)
    slug = AutoSlugField(always_update=True, populate_from='get_qualified_name', editable=True, unique=True)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)
    district = models.ForeignKey(District, models.SET_NULL, null=True, blank=True)
    parent = models.ForeignKey('Locality', models.SET_NULL, null=True, editable=False)
    latlong = models.PointField(null=True, blank=True)
    adjacent = models.ManyToManyField('Locality', related_name='neighbour', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta():
        ordering = ('name',)

    def __str__(self):
        return self.name or self.id

    def get_qualified_name(self):
        """Return the name and qualifier (e.g. 'Reepham, Lincs')"""
        if self.qualifier_name:
            return "%s, %s" % (self.name, self.qualifier_name)
        return str(self)

    def get_absolute_url(self):
        return reverse('locality_detail', args=(self.slug,))


class StopArea(models.Model):
    """A small area containing multiple stops, such as a bus station"""

    id = models.CharField(max_length=16, primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)

    TYPE_CHOICES = (
        ('GPBS', 'on-street pair'),
        ('GCLS', 'on-street cluster'),
        ('GAIR', 'airport building'),
        ('GBCS', 'bus/coach station'),
        ('GFTD', 'ferry terminal/dock'),
        ('GTMU', 'tram/metro station'),
        ('GRLS', 'rail station'),
        ('GCCH', 'coach service coverage'),
    )
    stop_area_type = models.CharField(max_length=4, choices=TYPE_CHOICES)

    parent = models.ForeignKey('StopArea', models.SET_NULL, null=True, editable=False)
    latlong = models.PointField(null=True)
    active = models.BooleanField()

    def __str__(self):
        return self.name


class Place(models.Model):
    source = models.ForeignKey('DataSource', models.CASCADE)
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    latlong = models.PointField(null=True, blank=True)
    polygon = models.PolygonField(null=True, blank=True)
    parent = models.ForeignKey('Place', models.SET_NULL, null=True, editable=False)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta():
        unique_together = ('source', 'code')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('place_detail', args=(self.pk,))


class StopPoint(models.Model):
    """The smallest type of geographical point.
    A point at which vehicles stop"""
    atco_code = models.CharField(max_length=16, primary_key=True)
    naptan_code = models.CharField(max_length=16, db_index=True, blank=True)

    common_name = models.CharField(max_length=48)
    landmark = models.CharField(max_length=48, blank=True)
    street = models.CharField(max_length=48, blank=True)
    crossing = models.CharField(max_length=48, blank=True)
    indicator = models.CharField(max_length=48, blank=True)

    latlong = models.PointField(null=True)

    stop_area = models.ForeignKey(StopArea, models.SET_NULL, null=True, editable=False)
    locality = models.ForeignKey('Locality', models.SET_NULL, null=True, editable=False)
    suburb = models.CharField(max_length=48, blank=True)
    town = models.CharField(max_length=48, blank=True)
    locality_centre = models.NullBooleanField()

    places = models.ManyToManyField(Place, blank=True)

    heading = models.PositiveIntegerField(null=True, blank=True)

    BEARING_CHOICES = (
        ('N', 'north ↑'),
        ('NE', 'north-east ↗'),
        ('E', 'east →'),
        ('SE', 'south-east ↘'),
        ('S', 'south ↓'),
        ('SW', 'south-west ↙'),
        ('W', 'west ←'),
        ('NW', 'north-west ↖')
    )
    bearing = models.CharField(max_length=2, choices=BEARING_CHOICES, blank=True)

    STOP_TYPE_CHOICES = (
        ('AIR', 'Airport entrance'),
        ('GAT', 'Air airside area'),
        ('FTD', 'Ferry terminal/dock entrance'),
        ('FER', 'Ferry/dock berth area'),
        ('FBT', 'Ferry berth'),  # ?
        ('RSE', 'Rail station entrance'),
        ('RLY', 'Rail platform access area'),
        ('RPL', 'Rail platform'),  # ?
        ('TMU', 'Tram/metro/underground entrance'),
        ('MET', 'MET'),  # ?
        ('PLT', 'Metro and underground platform access area'),
        ('BCE', 'Bus/coach station entrance'),
        ('BCS', 'Bus/coach bay/stand/stance within bus/coach station'),
        ('BCQ', 'Bus/coach bay'),  # ?
        ('BCT', 'On street bus/coach/tram stop'),
        ('TXR', 'Taxi rank (head of)'),
        ('STR', 'Shared taxi rank (head of)'),
    )
    stop_type = models.CharField(max_length=3, choices=STOP_TYPE_CHOICES, blank=True)

    BUS_STOP_TYPE_CHOICES = (
        ('MKD', 'Marked (pole, shelter etc)'),
        ('HAR', 'Hail and ride'),
        ('CUS', 'Custom (unmarked, or only marked on road)'),
        ('FLX', 'Flexible zone'),
    )
    bus_stop_type = models.CharField(max_length=3, choices=BUS_STOP_TYPE_CHOICES, blank=True)

    timing_status = models.CharField(max_length=3, choices=TIMING_STATUS_CHOICES, blank=True)

    admin_area = models.ForeignKey('AdminArea', models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(db_index=True)

    osm = JSONField(null=True, blank=True)

    class Meta():
        ordering = ('common_name', 'atco_code')

    def __str__(self):
        if self.indicator:
            return '%s (%s)' % (self.common_name, self.indicator)
        return self.common_name

    def get_heading(self):
        """Return the stop's bearing converted to degrees, for use with Google Street View."""
        if self.heading:
            return self.heading
        headings = {
            'N': 0,
            'NE': 45,
            'E': 90,
            'SE': 135,
            'S': 180,
            'SW': 225,
            'W': 270,
            'NW': 315,
        }
        return headings.get(self.bearing)

    prepositions = {
        'opp': 'opposite',
        'adj': 'adjacent to',
        'at': 'at',
        'o/s': 'outside',
        'nr': 'near',
        'before': 'before',
        'after': 'after',
        'by': 'by',
        'on': 'on',
        'in': 'in',
        'opposite': 'opposite',
        'outside': 'outside',
    }

    def get_qualified_name(self, short=True):
        if self.locality:
            locality_name = self.locality.name.replace(' Town Centre', '') \
                                                .replace(' City Centre', '')
            if short:
                locality_name = locality_name.replace('-next-the-Sea', '') \
                                                .replace(' Next The Sea', '') \
                                                .replace('North ', 'N ') \
                                                .replace('East ', 'E ') \
                                                .replace('South ', 'S ') \
                                                .replace('West ', 'W ')
            if self.common_name in locality_name:
                return locality_name.replace(self.common_name, str(self))  # Cardiff Airport
            if slugify(locality_name) not in slugify(self.common_name):
                if self.indicator in self.prepositions:
                    indicator = self.indicator
                    if not short:
                        indicator = self.prepositions[indicator]
                    return '%s, %s %s' % (locality_name, indicator, self.common_name)
                return '%s %s' % (locality_name, self)
        elif self.town not in self.common_name:
            return '{} {}'.format(self.town, self)
        return str(self)

    def get_long_name(self):
        return self.get_qualified_name(short=False)

    def get_region(self):
        if self.admin_area_id:
            return self.admin_area.region
        return Region.objects.filter(service__stops=self).first()

    def get_absolute_url(self):
        return reverse('stoppoint_detail', args=(self.atco_code,))

    def get_line_names(self):
        return [service.line_name for service in sorted(self.current_services, key=Service.get_order)]


class StopCode(models.Model):
    stop = models.ForeignKey('StopPoint', models.CASCADE)
    source = models.ForeignKey('DataSource', models.CASCADE)
    code = models.CharField(max_length=100)

    class Meta:
        unique_together = ('code', 'source')

    def __str__(self):
        return self.code


class DataSource(models.Model):
    name = models.CharField(max_length=255, unique=True)
    url = models.URLField(blank=True)
    datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class SIRISource(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    requestor_ref = models.CharField(max_length=255, blank=True)
    admin_areas = models.ManyToManyField(AdminArea, blank=True)

    def __str__(self):
        return self.name

    def get_poorly_key(self):
        return '{}:{}:poorly'.format(self.url, self.requestor_ref)

    def get_poorly(self):
        return cache.get(self.get_poorly_key())

    get_poorly.short_description = 'Poorly'
