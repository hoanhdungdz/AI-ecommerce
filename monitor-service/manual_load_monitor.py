import json
import os
import django
import sys

# Add current directory to path to find apps
sys.path.append('.')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'monitor_project.settings')
django.setup()

from monitor_app.models import monitor

def load_monitors():
    fixture_path = 'monitor_app/fixtures/initial_monitors.json'
    print(f"Loading from {fixture_path}...")
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    deleted_count, _ = monitor.objects.all().delete()
    print(f"Deleted {deleted_count} existing monitors.")
    
    for entry in data:
        fields = entry['fields']
        monitor, created = monitor.objects.update_or_create(
            id=entry['pk'],
            defaults={
                'name': fields['name'],
                'brand': fields['brand'],
                'price': fields['price'],
                'description': fields['description'],
                'quantity': fields['quantity']
            }
        )
        status = "Created" if created else "Updated"
        print(f"[{status}] monitor: {monitor.name}")

if __name__ == "__main__":
    load_monitors()

