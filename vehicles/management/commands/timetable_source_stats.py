import json
from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.utils import timezone
from ...models import DataSource


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        now = timezone.now()

        sources = DataSource.objects.annotate(
            count=Count('route__service', filter=Q(route__service__current=True), distinct=True),
        ).filter(count__gt=0)

        stats = {
            "datetime": now,
            "sources": {
                source.name: source.count
                for source in sources
            }
        }

        filename = "timetable-source-stats.json"

        try:
            with open(filename, 'r') as open_file:
                history = json.load(open_file)
                history = history[-3000:]
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            history = []

        history.append(stats)

        with open(filename, 'w') as open_file:
            json.dump(history, open_file, cls=DjangoJSONEncoder)
