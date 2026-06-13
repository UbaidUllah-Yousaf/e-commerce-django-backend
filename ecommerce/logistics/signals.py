import uuid

from django.db.models.signals import post_save
from django.dispatch import receiver

from logistics.models.shipment import Shipment
from logistics.tasks.shipments import process_custom_order


@receiver(post_save, sender="ecommerce.Order")
def enqueue_logistics_for_new_order(sender, instance, created, **kwargs):
    if not created:
        return
    if Shipment.objects.filter(ecommerce_order_id=instance.pk).exists():
        return
    process_custom_order.delay(instance.pk, correlation_id=str(uuid.uuid4()))
