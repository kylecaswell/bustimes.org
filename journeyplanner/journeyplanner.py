import requests
from django.conf import settings
from django.core.cache import cache


SESSION = requests.Session()


def journey(origin, destination):
    url = 'https://transportapi.com/v3/uk/public/journey/from/lonlat:{},{}/to/lonlat:{},{}.json'.format(
        origin.latlong.x, origin.latlong.y, destination.latlong.x, destination.latlong.y
    )
    json = cache.get(url)
    print(url)
    if not json:
        params = {
            'app_id': settings.TRANSPORTAPI_APP_ID,
            'app_key': settings.TRANSPORTAPI_APP_KEY,
        }
        json = SESSION.get(url, params=params).json()
        cache.set(url, json)
    return json
