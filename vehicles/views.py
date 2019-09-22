from datetime import timedelta
from requests import Session, exceptions
from ciso8601 import parse_datetime
from django.db.models import Exists, OuterRef, Prefetch, Subquery
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.http import last_modified
from django.views.generic.detail import DetailView
from django.urls import reverse
from django.utils import timezone
from multidb.pinning import use_primary_db
from busstops.views import get_bounding_box
from busstops.models import Operator, Service, ServiceCode, SIRISource, DataSource, Journey
from .models import Vehicle, VehicleLocation, VehicleJourney, VehicleEdit, Call
from .forms import EditVehiclesForm, EditVehicleForm
from .management.commands import import_sirivm
from .rifkind import rifkind
from .tasks import handle_siri_et


session = Session()


class Poorly(Exception):
    pass


class Vehicles():
    def __init__(self, operator):
        self.operator = operator

    def __str__(self):
        return 'Vehicles'

    def get_absolute_url(self):
        return reverse('operator_vehicles', args=(self.operator.slug,))


def get_vehicle_edit(vehicle, fields):
    edit = VehicleEdit(vehicle=vehicle)

    for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes'):
        if field in fields and str(fields[field]) != str(getattr(vehicle, field)):
            if fields[field]:
                setattr(edit, field, fields[field])
            else:
                setattr(edit, field, f'-{getattr(vehicle, field)}')

    if not edit.vehicle_type:
        edit.vehicle_type = ''

    if fields.get('colours'):
        if fields['colours'].isdigit():
            edit.livery_id = fields['colours']
        elif fields['colours']:
            edit.colours = fields['colours']

    return edit


def operator_vehicles(request, slug):
    operators = Operator.objects.select_related('region')
    try:
        operator = get_object_or_404(operators, slug=slug)
    except Http404:
        operator = get_object_or_404(operators, operatorcode__code=slug, operatorcode__source__name='slug')
    vehicles = operator.vehicle_set
    latest_journeys = Subquery(VehicleJourney.objects.filter(
        vehicle=OuterRef('pk')
    ).order_by('-datetime').values('pk')[:1])
    latest_journeys = vehicles.filter(latest_location=None).annotate(latest_journey=latest_journeys)
    latest_journeys = VehicleJourney.objects.filter(id__in=latest_journeys.values('latest_journey'))
    prefetch = Prefetch('vehiclejourney_set',
                        queryset=latest_journeys.select_related('service'), to_attr='latest_journeys')
    vehicles = vehicles.prefetch_related(prefetch)
    vehicles = vehicles.order_by('fleet_number', 'reg', 'code')
    vehicles = vehicles.select_related('vehicle_type', 'livery', 'latest_location__journey__service')

    edit = request.path.endswith('/edit')
    submitted = False
    if edit:
        form = EditVehiclesForm(request.POST, vehicle=vehicles[0])
        if request.POST and form.is_valid():
            ticked_vehicles = (vehicle for vehicle in vehicles if str(vehicle.id) in request.POST.getlist('vehicle'))
            data = {key: form.cleaned_data[key] for key in form.changed_data}
            submitted = len(VehicleEdit.objects.bulk_create(
                get_vehicle_edit(vehicle, data) for vehicle in ticked_vehicles
            ))
    else:
        form = None
        pending_edits = VehicleEdit.objects.filter(vehicle=OuterRef('id'))
        vehicles = vehicles.annotate(pending_edits=Exists(pending_edits))

    if not vehicles:
        raise Http404()

    return render(request, 'operator_vehicles.html', {
        'breadcrumb': [operator.region, operator],
        'object': operator,
        'today': timezone.localtime().date(),
        'vehicles': vehicles,
        'code_column': any(v.fleet_number_mismatch() for v in vehicles),
        'branding_column': any(vehicle.branding for vehicle in vehicles),
        'name_column': any(vehicle.name for vehicle in vehicles),
        'notes_column': any(vehicle.notes for vehicle in vehicles),
        'edit_url': reverse('admin:vehicles_vehicle_changelist'),
        'edit': edit,
        'submitted': submitted,
        'form': form,
    })


def get_locations(request):
    now = timezone.now()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(latest_vehicle__isnull=False, datetime__gte=fifteen_minutes_ago,
                                               current=True)

    try:
        bounding_box = get_bounding_box(request)
        locations = locations.filter(latlong__within=bounding_box)
    except KeyError:
        pass

    if 'service' in request.GET:
        locations = locations.filter(journey__service=request.GET['service'])

    return locations


@use_primary_db
def siri_one_shot(code, now):
    source = 'Icarus'
    siri_source = SIRISource.objects.get(name=code.scheme[:-5])
    line_name_cache_key = '{}:{}:{}'.format(siri_source.url, siri_source.requestor_ref, code.code)
    service_cache_key = '{}:{}'.format(code.service_id, source)
    if cache.get(line_name_cache_key):
        return 'cached (line name)'
    cached = cache.get(service_cache_key)
    if cached:
        return f'cached ({cached})'
    if siri_source.get_poorly():
        raise Poorly()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(latest_vehicle__isnull=False, journey__service=code.service_id,
                                               datetime__gte=fifteen_minutes_ago, current=True)
    scheduled_journeys = Journey.objects.filter(service=code.service_id, datetime__lt=now + timedelta(minutes=10),
                                                stopusageusage__datetime__gt=now - timedelta(minutes=10))
    if not scheduled_journeys.exists():
        if not locations.filter(journey__source__name=source).exists():
            # no journeys currently scheduled, and no vehicles online recently
            cache.set(service_cache_key, 'nothing scheduled', 300)  # back off for 5 minutes
            return 'nothing scheduled'
    # from a different source
    if locations.exclude(journey__source__name=source).exists():
        cache.set(service_cache_key, 'different source', 3600)  # back off for for 1 hour
        return 'deferring to a different source'
    cache.set(line_name_cache_key, 'line name', 40)  # cache for 40 seconds
    data = """<Siri xmlns="http://www.siri.org.uk/siri" version="1.3"><ServiceRequest><RequestorRef>{}</RequestorRef>
<VehicleMonitoringRequest version="1.3"><LineRef>{}</LineRef></VehicleMonitoringRequest>
</ServiceRequest></Siri>""".format(siri_source.requestor_ref, code.code)
    url = siri_source.url.replace('StopM', 'VehicleM', 1)
    response = session.post(url, data=data, timeout=5)
    if 'Client.AUTHENTICATION_FAILED' in response.text:
        cache.set(siri_source.get_poorly_key(), True, 3600)  # back off for an hour
        raise Poorly()
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='Icarus')
    for item in import_sirivm.items_from_response(response):
        command.handle_item(item, now, code)


schemes = ('Cornwall SIRI', 'Devon SIRI', 'Highland SIRI', 'Dundee SIRI', 'Bristol SIRI',
           'Leicestershire SIRI', 'Dorset SIRI', 'Hampshire SIRI', 'West Sussex SIRI', 'Bucks SIRI',
           'Peterborough SIRI')  # , 'Essex SIRI', 'Southampton SIRI', 'Slough SIRI', 'Staffordshire SIRI')


def vehicles_last_modified(request):
    request.nothing = False

    if 'service' in request.GET:
        service_id = request.GET['service']
        now = timezone.now()

        last_modified = cache.get(f'{service_id}:vehicles_last_modified')
        if last_modified and (now - last_modified).total_seconds() < 40:
            return last_modified

        codes = ServiceCode.objects.filter(scheme__in=schemes, service=service_id)
        for code in codes:
            try:
                siri_one_shot(code, now)
                break
            except (SIRISource.DoesNotExist, Poorly, exceptions.RequestException):
                continue

        if Operator.objects.filter(id__in=('KBUS', 'NCTR', 'TBTN', 'NOCT'), service=service_id).exists():
            rifkind(service_id)

        last_modified = cache.get(f'{service_id}:vehicles_last_modified')
        if not last_modified or (now - last_modified).total_seconds() > 900:  # older than 15 minutes
            request.nothing = True
        return last_modified

    locations = get_locations(request)
    try:
        location = locations.values('datetime').latest('datetime')
        request.nothing = False
        return location['datetime']
    except VehicleLocation.DoesNotExist:
        request.nothing = True
        return


@last_modified(vehicles_last_modified)
def vehicles_json(request):
    if request.nothing:
        locations = ()
    else:
        locations = get_locations(request).order_by()
        locations = locations.select_related('journey__vehicle__livery', 'journey__vehicle__vehicle_type')

        if 'service' in request.GET:
            extended = False
        else:
            extended = True
            locations = locations.select_related('journey__service', 'journey__vehicle__operator'
                                                 ).defer('journey__service__geometry')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [location.get_json(extended=extended) for location in locations]
    })


def service_vehicles_history(request, slug=None, operator=None, route=None):
    if slug:
        service = get_object_or_404(Service, slug=slug)
        journeys = service.vehiclejourney_set
    else:
        service = None
        operator = get_object_or_404(Operator, slug=operator)
        journeys = VehicleJourney.objects.filter(vehicle__operator=operator, route_name=route)
    date = request.GET.get('date')
    if date:
        try:
            date = parse_datetime(date).date()
        except ValueError:
            date = None
    dates = journeys.values_list('datetime__date', flat=True).distinct().order_by('datetime__date')
    if not date:
        date = dates.last()
        if not date:
            raise Http404()
    calls = Call.objects.filter(journey=OuterRef('pk'))
    locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
    journeys = journeys.filter(datetime__date=date).select_related('vehicle').annotate(calls=Exists(calls),
                                                                                       locations=Exists(locations))

    if slug:
        operator = service.operator.select_related('region').first()
    return render(request, 'vehicles/vehicle_detail.html', {
        'breadcrumb': [operator.region, operator, service or Vehicles(operator)],
        'date': date,
        'dates': dates,
        'object': service or route,
        'journeys': journeys.order_by('datetime'),
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region', 'vehicle_type', 'livery')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journeys = self.object.vehiclejourney_set
        dates = list(journeys.values_list('datetime__date', flat=True).distinct().order_by('datetime__date'))
        if self.object.operator:
            context['breadcrumb'] = [self.object.operator, Vehicles(self.object.operator)]

            context['previous'] = self.object.get_previous()
            context['next'] = self.object.get_next()

        if dates:
            context['dates'] = dates
            date = self.request.GET.get('date')
            if date:
                try:
                    date = parse_datetime(date).date()
                except ValueError:
                    date = None
            if not date:
                date = context['dates'][-1]
            context['date'] = date
            journeys = journeys.filter(datetime__date=date).order_by('datetime')
            calls = Call.objects.filter(journey=OuterRef('pk'))
            locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
            journeys = journeys.select_related('service').annotate(calls=Exists(calls), locations=Exists(locations))
            context['journeys'] = journeys
        return context


def edit_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle.objects.select_related('vehicle_type', 'livery', 'operator'), id=vehicle_id)
    submitted = False
    initial = {
        'fleet_number': vehicle.fleet_number,
        'reg': vehicle.reg,
        'vehicle_type': vehicle.vehicle_type,
        'colours': str(vehicle.livery_id or vehicle.colours),
        'notes': vehicle.notes
    }

    if request.method == 'POST':
        form = EditVehicleForm(request.POST, initial=initial, vehicle=vehicle)
        if not form.has_changed():
            form.add_error(None, 'You haven\'t changed anything')
        elif form.is_valid():
            edit = get_vehicle_edit(vehicle, {key: form.cleaned_data[key] for key in form.changed_data})
            edit.save()
            submitted = True
    else:
        form = EditVehicleForm(initial=initial, vehicle=vehicle)

    if vehicle.operator:
        breadcrumb = [vehicle.operator, Vehicles(vehicle.operator), vehicle]
    else:
        breadcrumb = [vehicle]

    return render(request, 'edit_vehicle.html', {
        'breadcrumb': breadcrumb,
        'form': form,
        'object': vehicle,
        'vehicle': vehicle,
        'previous': vehicle.get_previous(),
        'next': vehicle.get_next(),
        'submitted': submitted
    })


def tracking_report(request):
    week_ago = timezone.now() - timedelta(days=7)
    full_tracking = VehicleJourney.objects.filter(datetime__gt=week_ago)
    full_tracking = full_tracking.filter(service=OuterRef('pk')).exclude(source__name='Icarus')

    services = Service.objects.filter(current=True).annotate(full_tracking=Exists(full_tracking)).defer('geometry')
    prefetch = Prefetch('service_set', queryset=services)
    operators = Operator.objects.filter(
        service__current=True,
        service__tracking=True
    ).prefetch_related(prefetch).distinct()

    return render(request, 'vehicles/dashboard.html', {
        'operators': operators
    })


class JourneyDetailView(DetailView):
    model = VehicleJourney
    queryset = model.objects.select_related('vehicle', 'service')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['breadcrumb'] = [self.object.service]
        context['calls'] = self.object.call_set.order_by('visit_number').select_related('stop__locality')

        return context


def journey_json(request, pk):
    return JsonResponse([{
        'coordinates': tuple(location.latlong),
        'delta': location.early,
        'direction': location.heading,
        'datetime': location.datetime,
    } for location in VehicleLocation.objects.filter(journey=pk)], safe=False)


def siri(request):
    body = request.body.decode()
    if not body:
        return HttpResponse()
    if 'HeartbeatNotification>' in body:
        source = DataSource.objects.get(name='Arriva')
        source.datetime = timezone.now()
        source.save(update_fields=['datetime'])
    else:
        handle_siri_et.delay(body)
    return HttpResponse(f"""<?xml version="1.0" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
  <DataReceivedAcknowledgement>
    <ResponseTimestamp>{timezone.localtime().isoformat()}</ResponseTimestamp>
    <Status>true</Status>
  </DataReceivedAcknowledgement>
</Siri>""", content_type='text/xml')
