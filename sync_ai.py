import os
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from shop.models import Product

AI_SERVICE_URL = os.environ.get("AI_SERVICE_URL", "http://ai-service:8000").rstrip("/") + "/api/vectorize"

products = Product.objects.all()
print(f"Syncing {len(products)} products to AI Service...")

for p in products:
    data = {
        "product_id": str(p.id),
        "category": p.category.name if p.category else "Uncategorized",
        "name": p.name,
        "price": str(p.price),
        "description": p.description or "",
        "attributes": p.attributes
    }
    try:
        resp = requests.post(AI_SERVICE_URL, json=data, timeout=5)
        if resp.status_code == 200:
            print(f"✅ Synced: {p.name}")
        else:
            print(f"❌ Failed: {p.name} ({resp.status_code})")
    except Exception as e:
        print(f"❌ Error: {p.name} - {e}")
