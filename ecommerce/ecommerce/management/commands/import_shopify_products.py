from pathlib import Path

from django.core.management.base import BaseCommand

from ecommerce.shopify_csv_import import (
    load_bundled_demo_shopify_csvs,
    load_shopify_product_csv,
)


def default_template_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "fixtures" / "product_template.csv"


def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "fixtures"


class Command(BaseCommand):
    help = (
        "Import products from a Shopify product CSV export "
        "(same columns as Shopify admin product template)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            type=str,
            default=None,
            help=f"Path to CSV file. Default: bundled {default_template_path()}",
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Do not download remote product/variant images (faster, offline).",
        )
        parser.add_argument(
            "--all-demo",
            action="store_true",
            help=(
                "Import all bundled Shopify demo CSVs (product_template, apparel, "
                "home-and-garden, jewelery) from ecommerce/fixtures/."
            ),
        )

    def handle(self, *args, **options):
        if options["all_demo"]:
            stats = load_bundled_demo_shopify_csvs(
                fixtures_dir(),
                download_images=not options["no_images"],
                log=lambda m: self.stdout.write(m),
            )
        else:
            path = options["csv_path"]
            if not path:
                path = default_template_path()
            p = Path(path)
            if not p.is_file():
                self.stderr.write(self.style.ERROR(f"CSV not found: {p}"))
                return

            stats = load_shopify_product_csv(
                p,
                download_images=not options["no_images"],
                log=lambda m: self.stdout.write(m),
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Import finished.\n"
                f"  Product handles processed: {stats['product_handles']}\n"
                f"  Variants created: {stats['variants_created']}\n"
                f"  New collections: {stats['collections_created']}\n"
                f"  New tags: {stats['tags_created']}\n"
                f"  CSV product groups: {stats['groups']}\n"
            )
        )
