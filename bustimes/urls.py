from django.urls import path, re_path
from . import views


urlpatterns = [
    path('services/<slug>/debug', views.ServiceDebugView.as_view()),
    re_path(r'^sources/(?P<source>\d+)/routes/(?P<code>.*)', views.route_xml, name='route_xml'),
    path('stops/<atco_code>/times.json', views.stop_times_json),
    path('vehicles/tfl/<reg>', views.tfl_vehicle),
    path('trips/<int:pk>', views.TripDetailView.as_view(), name='trip_detail'),
    path('trips/<int:id>.json', views.trip_json),
    path('services-debug', views.services_debug),
]
