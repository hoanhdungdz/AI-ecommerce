import json
import os
import django
import sys

# Add current directory to path to find apps
sys.path.append('.')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartwatch_project.settings')
django.setup()

from smartwatch_app.models import Smartwatch

def load_smartwatches():
    fixture_path = 'smartwatch_app/fixtures/initial_smartwatches.json'
    print(f"Loading from {fixture_path}...")
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    deleted_count, _ = Smartwatch.objects.all().delete()
    print(f"Deleted {deleted_count} existing smartwatches.")
    
    for entry in data:
        fields = entry['fields']
        smartwatch, created = Smartwatch.objects.update_or_create(
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
        print(f"[{status}] smartwatch: {smartwatch.name}")

if __name__ == "__main__":
    load_smartwatches()
