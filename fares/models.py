from django.db import models
from django.contrib.postgres.fields import DateTimeRangeField
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe


# class Currency(models.TextChoices):
#     GBP = "GBP", "Pound Sterling"
#     EUR = "EUR", "Euro"


# currency = models.CharField(
#     max_length=3,
#     choices=Currency.choices,
#     default=Currency.GBP,
# )


class DataSet(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True)
    description = models.CharField(max_length=255)
    operators = models.ManyToManyField('busstops.Operator', blank=True)
    datetime = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('dataset_detail', args=(self.id,))

    def nice_name(self):
        return self.name.split("_", 1)[0]

    def credit(self):
        text = self.nice_name()

        if self.url:
            if "bus-data.dft.gov.uk" in self.url:
                text = f"{text}/Bus Open Data Service"

            text = format_html('<a href="{}">{}</a>', self.url, text)

        if self.datetime:
            date = self.datetime.strftime('%-d %B %Y')
            text = f'{text}, {date}'

        return mark_safe(f'<p class="credit">Fares data from {text}</p>')


class TimeInterval(models.Model):
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    def __str__(self):
        return self.description


class SalesOfferPackage(models.Model):
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    proof_required = models.CharField(max_length=255, blank=True)
    discount_basis = models.CharField(max_length=255, blank=True)
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


class TypeOfTariff(models.TextChoices):
    # DISTANCE_KILOMETERS = "Distance_kilometers", "Kilometer Distance Kilometers"
    # FLAT = "flat", "Flat"
    POINT_TO_PONT = "point_to_point", "Point to point"
    ZONAL = "zonal", "Zonal"
    # SECTION = "section", "Section"    # BANDED = "banded", "Section"
    # STORED_VALUE = "stored_value", "Stored value"
    # MULTITRIP = "multitrip", "Multitrip carnet"


class Tariff(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    services = models.ManyToManyField('busstops.Service', blank=True)
    operators = models.ManyToManyField('busstops.Operator', blank=True)
    source = models.ForeignKey(DataSet, models.CASCADE)
    filename = models.CharField(max_length=255)
    user_profile = models.ForeignKey(UserProfile, models.CASCADE, null=True, blank=True)
    trip_type = models.CharField(max_length=255)
    valid_between = DateTimeRangeField(null=True, blank=True)
    type_of_tariff = models.CharField(
        max_length=19,
        choices=TypeOfTariff.choices,
    )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tariff_detail', args=(self.id,))


class Price(models.Model):
    amount = models.DecimalField(max_digits=6, decimal_places=2)  # maximum £9999.99
    time_interval = models.ForeignKey(TimeInterval, models.CASCADE, null=True, blank=True)
    user_profile = models.ForeignKey(UserProfile, models.CASCADE, null=True, blank=True)
    sales_offer_package = models.ForeignKey(SalesOfferPackage, models.CASCADE, null=True, blank=True)
    tariff = models.ForeignKey(Tariff, models.CASCADE, null=True, blank=True)


class FareTable(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    user_profile = models.ForeignKey(UserProfile, models.CASCADE, null=True, blank=True)
    sales_offer_package = models.ForeignKey(SalesOfferPackage, models.CASCADE, null=True, blank=True)
    tariff = models.ForeignKey(Tariff, models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return self.tariff.get_absolute_url()


class FareZone(models.Model):
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    stops = models.ManyToManyField("busstops.StopPoint", blank=True)

    def __str__(self):
        return self.name


class DistanceMatrixElement(models.Model):
    code = models.CharField(max_length=255)
    price = models.ForeignKey(Price, models.CASCADE)
    start_zone = models.ForeignKey(FareZone, models.CASCADE, related_name='starting')
    end_zone = models.ForeignKey(FareZone, models.CASCADE, related_name='ending')
    tariff = models.ForeignKey(Tariff, models.CASCADE)

    def __str__(self):
        return self.code


class Column(models.Model):
    table = models.ForeignKey(FareTable, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return self.name.replace("/", "/\u200B")


class Row(models.Model):
    table = models.ForeignKey(FareTable, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(null=True, blank=True)


class Cell(models.Model):
    column = models.ForeignKey(Column, models.CASCADE)
    row = models.ForeignKey(Row, models.CASCADE)
    distance_matrix_element = models.ForeignKey(DistanceMatrixElement, models.CASCADE, null=True)
    price = models.ForeignKey(Price, models.CASCADE, null=True)
