import json
import os
import django
import sys

# Add current directory to path to find apps
sys.path.append('.')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tablet_project.settings')
django.setup()

from tablet_app.models import Tablet

def load_tablets():
    fixture_path = 'tablet_app/fixtures/initial_tablets.json'
    print(f"Loading from {fixture_path}...")
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    deleted_count, _ = Tablet.objects.all().delete()
    print(f"Deleted {deleted_count} existing tablets.")
    
    for entry in data:
        fields = entry['fields']
        tablet, created = Tablet.objects.update_or_create(
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
        print(f"[{status}] tablet: {tablet.name}")

if __name__ == "__main__":
    load_tablets()
