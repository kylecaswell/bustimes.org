import requests
from django.conf import settings
from django.core.cache import cache


SESSION = requests.Session()


def transportapi(origin, destination):
    if not (origin and destination):
        return

    url = 'https://transportapi.com/v3/uk/public/journey/from/lonlat:{},{}/to/lonlat:{},{}.json'.format(
        origin.latlong.x, origin.latlong.y, destination.latlong.x, destination.latlong.y
    )
    json = cache.get(url)
    if not json:
        params = settings.TRANSPORTAPI
        response = SESSION.get(url, params=params)
        print(response.url)
        json = response.json()
        cache.set(url, json)
    return json
