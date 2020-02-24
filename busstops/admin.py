from django.contrib import admin
from django.contrib.gis.forms import OSMWidget
from django.contrib.gis.db.models import PointField
from .models import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, StopCode,
    Place, SIRISource, DataSource
)


class AdminAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'atco_code', 'region_id')
    list_filter = ('region_id',)
    search_fields = ('atco_code',)


class StopCodeInline(admin.TabularInline):
    model = StopCode


class StopPointAdmin(admin.ModelAdmin):
    list_display = ('atco_code', 'naptan_code', 'locality', 'admin_area', '__str__')
    list_select_related = ('locality', 'admin_area')
    list_filter = ('stop_type', 'service__region', 'admin_area')
    raw_id_fields = ('places',)
    search_fields = ('atco_code', 'common_name', 'locality__name')
    ordering = ('atco_code',)
    formfield_overrides = {
        PointField: {'widget': OSMWidget}
    }
    inlines = [StopCodeInline]


class StopCodeAdmin(admin.ModelAdmin):
    list_display = ['stop', 'code', 'source']
    raw_id_fields = ['stop']


class LocalityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug')
    search_fields = ('id', 'name')
    raw_id_fields = ('adjacent',)
    list_filter = ('admin_area', 'admin_area__region')


class PlaceAdmin(admin.ModelAdmin):
    list_filter = ('source',)
    search_fields = ('name',)


class DataSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'datetime')


class SIRISourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'requestor_ref', 'areas', 'get_poorly')

    def get_queryset(self, _):
        return self.model.objects.prefetch_related('admin_areas')

    @staticmethod
    def areas(obj):
        return ', '.join('{} ({})'.format(area, area.atco_code) for area in obj.admin_areas.all())


admin.site.register(Region)
admin.site.register(AdminArea, AdminAreaAdmin)
admin.site.register(District)
admin.site.register(Locality, LocalityAdmin)
admin.site.register(StopArea)
admin.site.register(StopCode, StopCodeAdmin)
admin.site.register(StopPoint, StopPointAdmin)
admin.site.register(Place, PlaceAdmin)
admin.site.register(DataSource, DataSourceAdmin)
admin.site.register(SIRISource, SIRISourceAdmin)
