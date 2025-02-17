import requests
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Exists, OuterRef
from busstops.models import Operator, Service
from .models import VehicleType, VehicleFeature, Livery, Vehicle
from .fields import RegField


def get_livery_choices(operator):
    choices = {}
    vehicles = operator.vehicle_set.filter(withdrawn=False)
    liveries = Livery.objects.filter(vehicle__in=vehicles).annotate(popularity=Count('vehicle'))
    for livery in liveries.order_by('-popularity').distinct():
        choices[livery.id] = livery
    for vehicle in vehicles.distinct('colours'):
        if not vehicle.livery_id and vehicle.colours and vehicle.colours != 'Other':
            choices[vehicle.colours] = Livery(colours=vehicle.colours, name=f'Like {vehicle}')
    choices = [(key, livery.preview(name=True)) for key, livery in choices.items()]
    if choices:
        choices = [('', 'None/mostly white')] + choices + [('Other', 'Other')]
    return choices


class EditVehiclesForm(forms.Form):
    operator = forms.ModelChoiceField(queryset=None, label='Operator', empty_label='')
    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects, label='Type', required=False, empty_label='')
    colours = forms.ChoiceField(label='Livery', widget=forms.RadioSelect, required=False)
    other_colour = forms.CharField(widget=forms.TextInput(attrs={"type": "color"}), required=False)
    features = forms.ModelMultipleChoiceField(queryset=VehicleFeature.objects, label='Features',
                                              widget=forms.CheckboxSelectMultiple, required=False)
    depot = forms.ChoiceField(required=False)
    withdrawn = forms.BooleanField(label='Permanently withdrawn', required=False)

    def clean_url(self):
        if self.cleaned_data['url']:
            try:
                response = requests.get(self.cleaned_data['url'], timeout=5)
                if response.ok:
                    return self.cleaned_data['url']
            except requests.RequestException:
                pass
            raise ValidationError('That URL doesn’t work for me. Maybe it’s too long, or Facebook')

    def clean_other_colour(self):
        if self.cleaned_data['other_colour']:
            if self.cleaned_data.get('colours') != 'Other':
                return
        return self.cleaned_data['other_colour']

    def has_really_changed(self):
        if not self.has_changed():
            return False
        if all(key == 'url' for key in self.changed_data):
            return False
        return True

    def __init__(self, *args, operator=None, user, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)

        colours = None
        depots = None

        if operator:
            colours = get_livery_choices(operator)

            if user.trusted:
                depots = operator.vehicle_set.distinct('data__Depot').values_list('data__Depot', flat=True)
                depots = [(depot, depot) for depot in depots if depot]
                depots.sort()
            elif vehicle and vehicle.data and 'Depot' in vehicle.data:
                depots = [(vehicle.data['Depot'], vehicle.data['Depot'])]

        if colours:
            self.fields['colours'].choices = colours
        else:
            del self.fields['colours']
            del self.fields['other_colour']

        if depots:
            self.fields['depot'].choices = [('', '')] + depots
        else:
            del self.fields['depot']

        operators = None
        if vehicle and (not operator or operator.parent):
            operators = Operator.objects
            if user.trusted and operator:
                # any sibling operator
                operators = operators.filter(parent=operator.parent)
                condition = Exists(Service.objects.filter(current=True, operator=OuterRef('pk')).only('id'))
                condition |= Exists(Vehicle.objects.filter(operator=OuterRef('pk')).only('id'))
            else:
                # only operators whose services the vehicle has operated
                condition = Exists(vehicle.vehiclejourney_set.filter(service__operator=OuterRef('pk')))
            if operator:
                condition |= Q(pk=operator.pk)
            self.fields['operator'].queryset = operators.filter(condition)
        else:
            del self.fields['operator']


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle
    """
    fleet_number = forms.CharField(required=False, max_length=14)
    reg = RegField(label='Number plate', required=False, max_length=10)
    branding = forms.CharField(label="Other branding", required=False, max_length=255)
    name = forms.CharField(label='Name', help_text="Not your name", required=False, max_length=255)
    previous_reg = RegField(required=False, max_length=14)
    depot = forms.ChoiceField(required=False)
    notes = forms.CharField(  # help_text="""Please <strong>don’t</strong>
                              # add information about depots, previous operators, etc""",
                            required=False, max_length=255)
    url = forms.URLField(label='URL', help_text="Optional link to a public (not Facebook) web page or photo "
                         "showing repaint", required=False, max_length=255)
    field_order = ['fleet_number', 'reg', 'operator', 'vehicle_type', 'colours', 'other_colour', 'branding', 'name',
                   'previous_reg', 'features', 'depot', 'notes']

    def __init__(self, *args, user, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs, user=user, vehicle=vehicle)

        if str(vehicle.fleet_number) in vehicle.code:
            self.fields['fleet_number'].disabled = True
        if vehicle.reg and vehicle.reg in vehicle.code.replace('_', '').replace(' ', '').replace('-', ''):
            self.fields['reg'].disabled = True

        if not user.is_staff:
            if not vehicle.notes:
                del self.fields['notes']
            if not vehicle.branding:
                del self.fields['branding']
