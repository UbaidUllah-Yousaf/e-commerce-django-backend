from django.core.management import call_command
from django.core.management.base import BaseCommand

from logistics.models.config import FulfillmentConfiguration
from logistics.models.courier import CourierConfiguration
from logistics.models.rules import CityFulfillmentRule
from logistics.models.shopify import ShopifyConfiguration


class Command(BaseCommand):
    help = (
        "Load logistics sandbox fixture (couriers, city rules, fulfillment config, "
        "Shopify demo). Use: python manage.py loaddata logistics_sandbox"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing logistics config rows before loading fixture.",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            CityFulfillmentRule.objects.all().delete()
            FulfillmentConfiguration.objects.filter(pk=1).delete()
            ShopifyConfiguration.objects.all().delete()
            CourierConfiguration.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared logistics configuration tables."))

        call_command("loaddata", "logistics_sandbox", verbosity=options.get("verbosity", 1))

        quiqup = CourierConfiguration.objects.filter(courier_name="Quiqup").first()
        rules = CityFulfillmentRule.objects.filter(is_active=True).count()
        couriers = CourierConfiguration.objects.filter(is_active=True).count()
        shops = ShopifyConfiguration.objects.count()

        self.stdout.write(self.style.SUCCESS("Loaded fixture: logistics_sandbox"))
        self.stdout.write(f"  Couriers (active): {couriers}")
        self.stdout.write(f"  City rules (active): {rules}")
        self.stdout.write(f"  Shopify stores: {shops}")
        if quiqup and quiqup.api_credentials.get("api_key"):
            key = quiqup.api_credentials["api_key"]
            masked = f"{key[:6]}...{key[-4:]}" if len(key) > 12 else "(set)"
            self.stdout.write(f"  Quiqup API key in fixture: {masked}")
        self.stdout.write("")
        self.stdout.write("Load only (no wrapper):")
        self.stdout.write("  python manage.py loaddata logistics_sandbox")
