import json
import os
import django
import sys

# Add current directory to path to find apps
sys.path.append('.')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'accessory_project.settings')
django.setup()

from accessory_app.models import Accessory

def load_accessories():
    fixture_path = 'accessory_app/fixtures/initial_accessories.json'
    print(f"Loading from {fixture_path}...")
    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    deleted_count, _ = Accessory.objects.all().delete()
    print(f"Deleted {deleted_count} existing accessories.")
    
    for entry in data:
        fields = entry['fields']
        accessory, created = Accessory.objects.update_or_create(
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
        print(f"[{status}] accessory: {accessory.name}")

if __name__ == "__main__":
    load_accessories()
