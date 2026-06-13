"""Keep Order / OrderLineItem fulfillment_status in sync with Fulfillment rows."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from ecommerce.models.fulfillment import (
    Fulfillment,
    FulfillmentLineItem,
    recompute_fulfillment_statuses_for_order,
)


def _recompute(order_id: int | None) -> None:
    if order_id:
        recompute_fulfillment_statuses_for_order(order_id)


@receiver(post_save, sender=Fulfillment)
def _fulfillment_saved(sender, instance, **kwargs):
    _recompute(instance.order_id)


@receiver(post_delete, sender=Fulfillment)
def _fulfillment_deleted(sender, instance, **kwargs):
    _recompute(instance.order_id)


@receiver(post_save, sender=FulfillmentLineItem)
def _fulfillment_line_item_saved(sender, instance, **kwargs):
    _recompute(instance.fulfillment.order_id)


@receiver(post_delete, sender=FulfillmentLineItem)
def _fulfillment_line_item_deleted(sender, instance, **kwargs):
    _recompute(instance.fulfillment.order_id)
