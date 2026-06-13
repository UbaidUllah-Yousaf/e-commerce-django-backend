# ecommerce/management/commands/dummy_data.py — seed catalog from Shopify-style collections JSON or CSV.

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ecommerce.constants.product import PRODUCT_STATUS_ACTIVE
from ecommerce.models.collection import Collection
from ecommerce.models.product import (
    Product,
    ProductVariant,
    ProductOption,
    ProductOptionValue,
)
from ecommerce.models.tag import Tag
from ecommerce.shopify_csv_import import (
    download_image,
    load_bundled_demo_shopify_csvs,
    load_shopify_product_csv,
)


BUNDLED_COLLECTIONS_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures"
    / "shopify_collections_demo.json"
)


class Command(BaseCommand):
    help = (
        "Seed the store from bundled Shopify-style collections JSON "
        f"({BUNDLED_COLLECTIONS_JSON.name}), or import Shopify product CSV (--shopify-csv)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            type=str,
            default=None,
            help=(
                "Path to a JSON file with a top-level \"collections\" array "
                f"(default: bundled {BUNDLED_COLLECTIONS_JSON.name})."
            ),
        )
        parser.add_argument(
            "--shopify-csv",
            type=str,
            nargs="?",
            const="bundled",
            default=None,
            help=(
                "Import Shopify product CSV instead of JSON. "
                "Pass a file path; use 'bundled' for product_template.csv only; "
                "use 'bundled-all' for all demo CSVs in ecommerce/fixtures/."
            ),
        )
        parser.add_argument(
            "--no-images",
            action="store_true",
            help="Skip downloading remote images (JSON and CSV import).",
        )

    def handle(self, *args, **kwargs):
        Product.all_objects.all().hard_delete()
        Collection.all_objects.all().hard_delete()

        shopify_arg = kwargs.get("shopify_csv")
        if shopify_arg is not None:
            fixtures = Path(__file__).resolve().parent.parent.parent / "fixtures"
            download_images = not kwargs.get("no_images", False)
            if shopify_arg == "bundled-all":
                stats = load_bundled_demo_shopify_csvs(
                    fixtures,
                    download_images=download_images,
                    log=lambda m: self.stdout.write(m),
                )
            elif shopify_arg == "bundled":
                csv_path = fixtures / "product_template.csv"
                if not csv_path.is_file():
                    self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
                    return
                stats = load_shopify_product_csv(
                    csv_path,
                    download_images=download_images,
                    log=lambda m: self.stdout.write(m),
                )
            else:
                csv_path = Path(shopify_arg)
                if not csv_path.is_file():
                    self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
                    return
                stats = load_shopify_product_csv(
                    csv_path,
                    download_images=download_images,
                    log=lambda m: self.stdout.write(m),
                )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Shopify CSV import done. Variants: {stats['variants_created']}, "
                    f"handles: {stats['product_handles']}, groups: {stats['groups']}"
                )
            )
            return

        json_arg = kwargs.get("json")
        path = Path(json_arg) if json_arg else BUNDLED_COLLECTIONS_JSON
        if not path.is_file():
            self.stderr.write(self.style.ERROR(f"JSON not found: {path}"))
            return

        with path.open(encoding="utf-8") as f:
            payload = json.load(f)

        self._seed_from_collections_json(
            payload,
            download_images=not kwargs.get("no_images", False),
        )

    @transaction.atomic
    def _seed_from_collections_json(self, payload: dict, *, download_images: bool) -> None:
        collections_data = payload.get("collections")
        if not isinstance(collections_data, list):
            self.stderr.write(
                self.style.ERROR('JSON must contain a "collections" array.')
            )
            return

        self.stdout.write(self.style.WARNING("Creating collections and products..."))

        for coll in collections_data:
            if not isinstance(coll, dict):
                continue
            handle = (coll.get("handle") or "").strip()
            title = (coll.get("title") or handle or "Untitled").strip()[:255]
            if not handle:
                self.stderr.write(self.style.WARNING(f"Skipping collection without handle: {title!r}"))
                continue

            collection = Collection.objects.create(
                handle=handle[:50],
                title=title,
                description=(coll.get("description") or "")[:2000],
                is_active=True,
            )

            img_block = coll.get("image") or {}
            coll_src = ""
            if isinstance(img_block, dict):
                coll_src = (img_block.get("src") or "").strip()
            if download_images and coll_src:
                cf = download_image(coll_src, f"coll-{handle}")
                if cf:
                    collection.image.save(cf.name, cf, save=True)

            products = coll.get("products") or []
            if not isinstance(products, list):
                continue

            for prod in products:
                if not isinstance(prod, dict):
                    continue
                self._import_product(
                    prod,
                    collection,
                    download_images=download_images,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "\n".join(
                    [
                        "",
                        "==================================================",
                        "",
                        "Store seeded successfully!",
                        "",
                        f"Collections: {Collection.objects.count()}",
                        f"Products: {Product.objects.count()}",
                        f"Variants: {ProductVariant.objects.count()}",
                        f"Tags: {Tag.objects.count()}",
                        "",
                        "==================================================",
                        "",
                    ]
                )
            )
        )

    def _import_product(
        self,
        prod: dict,
        collection: Collection,
        *,
        download_images: bool,
    ) -> None:
        phandle = (prod.get("handle") or "").strip()
        ptitle = (prod.get("title") or phandle or "Product").strip()[:255]
        if not phandle:
            self.stderr.write(self.style.WARNING(f"Skipping product without handle: {ptitle!r}"))
            return

        description = (prod.get("description") or "").strip()
        product = Product.objects.create(
            handle=phandle[:50],
            title=ptitle,
            description=description,
            body_html="",
            collection=collection,
            vendor=(prod.get("vendor") or "")[:255],
            product_type=(prod.get("product_type") or "")[:255],
            status=PRODUCT_STATUS_ACTIVE,
            is_published=True,
            published_at=timezone.now(),
        )

        tag_objs: list[Tag] = []
        for raw in prod.get("tags") or []:
            if not isinstance(raw, str):
                continue
            name = raw.strip()
            if not name:
                continue
            tag, _ = Tag.objects.get_or_create(name=name[:100])
            tag_objs.append(tag)
        if tag_objs:
            product.tags.set(tag_objs)

        images = prod.get("images") or []
        featured_url = ""
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict):
                featured_url = (first.get("src") or "").strip()
        if download_images and featured_url:
            cf = download_image(featured_url, phandle)
            if cf:
                product.featured_image.save(cf.name, cf, save=True)

        options_list = prod.get("options") or []
        if not isinstance(options_list, list):
            options_list = []

        option_models: list[ProductOption] = []
        value_by_option_and_label: dict[tuple[int, str], ProductOptionValue] = {}

        for opt in options_list:
            if not isinstance(opt, dict):
                continue
            oname = (opt.get("name") or "").strip()[:100]
            if not oname:
                continue
            po, _ = ProductOption.objects.get_or_create(product=product, name=oname)
            option_models.append(po)
            for val in opt.get("values") or []:
                if not isinstance(val, str):
                    continue
                v = val.strip()[:100]
                if not v:
                    continue
                pov, _ = ProductOptionValue.objects.get_or_create(option=po, value=v)
                value_by_option_and_label[(po.id, v)] = pov

        variants = prod.get("variants") or []
        if not isinstance(variants, list):
            return

        for var in variants:
            if not isinstance(var, dict):
                continue
            sku = (var.get("sku") or "").strip()[:100] or None
            price = self._decimal_field(var.get("price"))
            if price is None:
                self.stderr.write(
                    self.style.WARNING(f"Skipping variant without price (product {phandle})")
                )
                continue

            compare_raw = var.get("compare_at_price")
            compare_at = self._decimal_field(compare_raw) if compare_raw not in (None, "") else None

            inv = var.get("inventory_quantity")
            try:
                inventory_quantity = max(0, int(inv)) if inv is not None else 0
            except (TypeError, ValueError):
                inventory_quantity = 0

            vtitle = (var.get("title") or sku or "Default").strip()[:255]

            variant = ProductVariant.objects.create(
                product=product,
                title=vtitle,
                sku=sku,
                price=price,
                compare_at_price=compare_at,
                inventory_quantity=inventory_quantity,
                is_active=True,
            )

            m2m: list[ProductOptionValue] = []
            for idx, po in enumerate(option_models):
                key = f"option{idx + 1}"
                choice = var.get(key)
                if choice is None or choice == "":
                    continue
                label = str(choice).strip()[:100]
                pov = value_by_option_and_label.get((po.id, label))
                if pov is not None:
                    m2m.append(pov)
            if m2m:
                variant.option_values.set(m2m)

            v_img = (var.get("image") or "").strip()
            if download_images and v_img:
                cf = download_image(v_img, sku or phandle)
                if cf:
                    variant.image.save(cf.name, cf, save=True)

    @staticmethod
    def _decimal_field(raw) -> Decimal | None:
        if raw is None or raw == "":
            return None
        try:
            return Decimal(str(raw).replace(",", ""))
        except (InvalidOperation, ValueError):
            return None
