from django.core.management.base import BaseCommand

from logistics.models.shipment import Shipment
from logistics.services.ecommerce_fulfillment_sync import sync_ecommerce_fulfillment_from_shipment


class Command(BaseCommand):
    help = "Sync ecommerce Fulfillment rows from logistics shipments (Shopify fulfillment records)."

    def add_arguments(self, parser):
        parser.add_argument("--order-id", type=int, help="Only sync this ecommerce order id.")

    def handle(self, *args, **options):
        qs = Shipment.objects.filter(ecommerce_order_id__isnull=False).order_by("id")
        if options.get("order_id"):
            qs = qs.filter(ecommerce_order_id=options["order_id"])
        count = 0
        for shipment in qs:
            if sync_ecommerce_fulfillment_from_shipment(shipment):
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Synced {count} fulfillment(s) from {qs.count()} shipment(s)."))
