import json
import logging
import threading
import requests
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product

logger = logging.getLogger(__name__)

# FastAPI AI Service Endpoint (trong Docker network)
AI_SERVICE_URL = f"{settings.AI_SERVICE_URL.rstrip('/')}/api/vectorize"


def _send_to_ai_service(product_data):
    """Gửi dữ liệu sản phẩm đến AI Service trong background thread."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(
                AI_SERVICE_URL,
                json=product_data,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            if response.status_code in [200, 201]:
                logger.info(f"✅ Synced product {product_data['product_id']} to Vector DB.")
                return
            else:
                logger.warning(
                    f"⚠️ Sync product {product_data['product_id']} failed "
                    f"(attempt {attempt + 1}/{max_retries}). Status: {response.status_code}"
                )
        except requests.exceptions.ConnectionError:
            logger.warning(
                f"⚠️ AI Service chưa sẵn sàng (attempt {attempt + 1}/{max_retries}). "
                f"Product {product_data['product_id']} sẽ thử lại..."
            )
        except Exception as e:
            logger.error(f"❌ Error syncing product {product_data['product_id']}: {e}")
            return

        # Chờ trước khi retry
        import time
        time.sleep(2 * (attempt + 1))

    logger.error(f"❌ Không thể sync product {product_data['product_id']} sau {max_retries} lần thử.")


@receiver(post_save, sender=Product)
def sync_product_to_vector_db(sender, instance, created, **kwargs):
    """
    Signal: Khi Product được tạo/cập nhật → gửi dữ liệu sang AI Service
    để vectorize lưu vào ChromaDB (Vector Database).
    
    Sử dụng background thread để không block Django request.
    """
    try:
        data = {
            "product_id": str(instance.id),
            "category": instance.category.name if instance.category else "Uncategorized",
            "name": instance.name,
            "price": str(instance.price),
            "description": instance.description or "",
            "attributes": instance.attributes
        }

        # Gửi trong background thread để không block request
        thread = threading.Thread(target=_send_to_ai_service, args=(data,))
        thread.daemon = True
        thread.start()

        action = "created" if created else "updated"
        logger.info(f"📤 Product {instance.id} {action}, queued for AI sync.")

    except Exception as e:
        logger.error(f"❌ Error preparing product {instance.id} for sync: {e}")
