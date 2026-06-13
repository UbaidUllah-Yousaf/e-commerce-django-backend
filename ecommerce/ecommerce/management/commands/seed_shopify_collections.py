# ecommerce/management/commands/seed_shopify_collections.py

from django.core.management import call_command
from django.core.management.base import BaseCommand

from ecommerce.management.commands.dummy_data import BUNDLED_COLLECTIONS_JSON


class Command(BaseCommand):
    help = (
        "Seed the catalog from Shopify-style collections JSON "
        f"(default: {BUNDLED_COLLECTIONS_JSON}). "
        "Same as: python manage.py dummy_data [--json PATH] [--no-images]"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            type=str,
            default=None,
            help=(
                "Path to JSON with a top-level \"collections\" array "
                f"(default: bundled {BUNDLED_COLLECTIONS_JSON.name})."
            ),
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Skip downloading remote images.",
        )

    def handle(self, *args, **options):
        kwargs = {}
        if options.get("json"):
            kwargs["json"] = options["json"]
        if options.get("no_images"):
            kwargs["no_images"] = True
        call_command("dummy_data", **kwargs)
