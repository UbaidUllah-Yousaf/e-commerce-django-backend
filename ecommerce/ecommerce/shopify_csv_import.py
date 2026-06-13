"""
Import Shopify product export CSV into Django models (Product, variants, options, tags, images).
Column names match Shopify's product CSV template (e.g. product_template.csv).
"""

from __future__ import annotations

import csv
import os
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from pathlib import Path
from typing import BinaryIO, Callable, TextIO
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify

from ecommerce.models.collection import Collection
from ecommerce.models.product import (
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
)
from ecommerce.models.tag import Tag

# Bundled demo exports (admin "new" template + classic Shopify product CSVs).
SHOPIFY_DEMO_PRODUCT_CSV_FILENAMES = (
    "product_template.csv",
    "apparel.csv",
    "home-and-garden.csv",
    "jewelery.csv",
)


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool_shopify(val: str) -> bool:
    return _clean(val).upper() in ("TRUE", "YES", "1", "Y")


def _decimal(val: str | None) -> Decimal | None:
    s = _clean(val)
    if not s:
        return None
    try:
        return Decimal(s.replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _int(val: str | None, default: int = 0) -> int:
    s = _clean(val)
    if not s:
        return default
    try:
        return int(float(s))
    except ValueError:
        return default


def _status(val: str) -> str:
    m = _clean(val).lower()
    if m in ("active", "draft", "archived"):
        return m
    return "draft"


def _collection_from_row(row: dict) -> tuple[str, str, str]:
    """Return (handle, title, description_hint) for a Collection."""
    category = _clean(row.get("Product category"))
    ptype = _clean(row.get("Type"))
    if category:
        parts = [p.strip() for p in category.split(">") if p.strip()]
        title = parts[-1] if parts else ptype or "General"
        handle = slugify(parts[0])[:80] if parts else slugify(title)
    else:
        title = ptype or "General"
        handle = slugify(title)[:80] or "general"
    desc = category or title
    return handle, title[:255], desc


def download_image(url: str, basename: str, timeout: int = 60) -> ContentFile | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; EcommerceImport/1.0)"},
        )
        resp.raise_for_status()
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", basename)[:60].strip("-") or "image"
        return ContentFile(resp.content, name=f"{safe}-{uuid.uuid4().hex[:8]}{ext}")
    except (requests.RequestException, OSError, ValueError):
        return None


def iter_option_pairs(row: dict) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for i in range(1, 4):
        name = _clean(row.get(f"Option{i} name"))
        val = _clean(row.get(f"Option{i} value"))
        if name and val:
            pairs.append((name, val))
    return pairs


def normalize_shopify_product_row(row: dict) -> dict:
    """
    Map Shopify "classic" export columns (Handle, Variant SKU, Image Src, …)
    onto the same keys used by the admin product_template.csv importer.
    """
    r: dict[str, str | None] = {}
    for k, v in row.items():
        if k is None:
            continue
        key = _clean(k)
        r[key] = v

    def g(*keys: str) -> str:
        for key in keys:
            if key not in r:
                continue
            s = _clean(r.get(key))
            if s:
                return s
        return ""

    handle = g("URL handle", "Handle")

    raw_desc = g("Description")
    body_col = g("Body (HTML)")
    if body_col:
        body_html_out = body_col
        plain_desc = strip_tags(body_col) or ""
    elif raw_desc:
        if "<" in raw_desc:
            body_html_out = raw_desc
            plain_desc = strip_tags(raw_desc)
        else:
            body_html_out = ""
            plain_desc = raw_desc
    else:
        body_html_out = ""
        plain_desc = ""

    pub = g("Published on online store", "Published")
    if not pub:
        pub = "true"

    status = g("Status")
    if not status:
        status = "active" if _bool_shopify(pub) else "draft"

    pscope = g("Published scope").lower()
    if pscope not in ("web", "global", "none"):
        pscope = "web"

    out: dict[str, str] = {
        "URL handle": handle,
        "Title": g("Title"),
        "Description": plain_desc,
        "Body HTML": body_html_out,
        "Vendor": g("Vendor"),
        "Product category": g("Product category"),
        "Type": g("Type"),
        "Tags": g("Tags"),
        "Published on online store": pub,
        "Published scope": pscope,
        "Status": status,
        "SEO title": g("SEO title", "SEO Title"),
        "SEO description": g("SEO description", "SEO Description"),
        "Template suffix": g("Template suffix", "Template Suffix"),
        "Gift card": g("Gift card"),
        "SKU": g("SKU", "Variant SKU"),
        "Barcode": g("Barcode", "Variant Barcode"),
        "Price": g("Price", "Variant Price"),
        "Compare-at price": g("Compare-at price", "Variant Compare At Price"),
        "Cost per item": g("Cost per item"),
        "Inventory quantity": g("Inventory quantity", "Variant Inventory Qty"),
        "Weight value (grams)": g("Weight value (grams)", "Variant Grams"),
        "Product image URL": g("Product image URL", "Image Src"),
        "Variant image URL": g("Variant image URL", "Variant Image"),
    }
    for i in (1, 2, 3):
        out[f"Option{i} name"] = g(f"Option{i} name", f"Option{i} Name")
        out[f"Option{i} value"] = g(f"Option{i} value", f"Option{i} Value")
    return out


def _derive_variant_sku_base(handle: str, option_pairs: list[tuple[str, str]]) -> str:
    h = slugify(handle)[:40] or "variant"
    parts = [h]
    for _name, val in option_pairs:
        seg = slugify(val)[:24]
        if seg:
            parts.append(seg)
    if len(parts) == 1:
        parts.append("default")
    return "-".join(parts)[:100]


def _allocate_unique_sku(base: str, used: set[str]) -> str:
    candidate = base[:100]
    if candidate not in used:
        return candidate
    n = 2
    while True:
        suffix = f"-{n}"
        candidate = f"{base[: 100 - len(suffix)]}{suffix}"
        if candidate not in used:
            return candidate
        n += 1


def _merge_product_row(rows: list[dict]) -> dict:
    """Primary row = first with Title; fill missing keys from any row in the group."""
    primary_idx = 0
    for i, r in enumerate(rows):
        if _clean(r.get("Title")):
            primary_idx = i
            break
    out = dict(rows[primary_idx])
    for r in rows:
        for k, v in r.items():
            if not _clean(out.get(k)) and _clean(v):
                out[k] = v
    return out


def load_shopify_product_csv(
    source: str | Path | TextIO | BinaryIO,
    *,
    download_images: bool = True,
    log: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """
    Parse Shopify-format CSV and create/update products.

    Returns counts: products_created, variants_created, collections_created, tags_created.
    """
    log = log or (lambda _m: None)

    if isinstance(source, (str, Path)):
        path = Path(source)
        f = path.open("r", encoding="utf-8-sig", newline="")
        close_f = True
    else:
        f = source
        close_f = False
        if isinstance(f, BinaryIO):
            f = TextIOWrapper(f, encoding="utf-8-sig", newline="")

    reader = csv.DictReader(f)
    if not reader.fieldnames:
        if close_f:
            f.close()
        raise ValueError("CSV has no header row.")

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in reader:
        norm = normalize_shopify_product_row(dict(row))
        handle = _clean(norm.get("URL handle"))
        if not handle:
            continue
        groups[handle].append(norm)

    if close_f:
        f.close()

    products_touched = 0
    variants_created = 0
    collections_created = 0
    tags_created = 0

    for handle, rows in groups.items():
        if not rows:
            continue
        meta = _merge_product_row(rows)
        title = _clean(meta.get("Title")) or handle.replace("-", " ").title()
        description = _clean(meta.get("Description"))
        body_html = _clean(meta.get("Body HTML"))
        vendor = _clean(meta.get("Vendor"))
        product_type = _clean(meta.get("Type"))
        product_category = _clean(meta.get("Product category"))
        tags_str = _clean(meta.get("Tags"))
        seo_title = _clean(meta.get("SEO title"))[:255]
        seo_description = _clean(meta.get("SEO description"))
        template_suffix = _clean(meta.get("Template suffix"))[:255]
        gift_card = _bool_shopify(meta.get("Gift card"))
        pscope = _clean(meta.get("Published scope")).lower()
        if pscope not in ("web", "global", "none"):
            pscope = "web"
        published = _bool_shopify(
            _clean(meta.get("Published on online store")) or "TRUE"
        )
        status = _status(meta.get("Status", "draft"))

        existing = Product.all_objects.filter(handle=handle).only("published_at").first()
        if published:
            published_at = (
                existing.published_at
                if existing and existing.published_at
                else timezone.now()
            )
        else:
            published_at = None

        ch, ctitle, cdesc = _collection_from_row(meta)
        collection, c_created = Collection.all_objects.update_or_create(
            handle=ch,
            defaults={
                "title": ctitle,
                "description": cdesc[:2000] if cdesc else "",
                "is_active": True,
                "deleted_at": None,
            },
        )
        if c_created:
            collections_created += 1
            if download_images:
                img_url = _clean(meta.get("Product image URL"))
                if img_url and not collection.image:
                    cf = download_image(img_url, f"coll-{ch}")
                    if cf:
                        collection.image.save(cf.name, cf, save=True)

        with transaction.atomic():
            product, _p_created = Product.all_objects.update_or_create(
                handle=handle,
                defaults={
                    "title": title[:255],
                    "description": description,
                    "body_html": body_html,
                    "collection": collection,
                    "vendor": vendor[:255],
                    "product_type": product_type[:255],
                    "product_category": product_category,
                    "status": status,
                    "is_published": published,
                    "published_at": published_at,
                    "published_scope": pscope,
                    "seo_title": seo_title,
                    "seo_description": seo_description,
                    "template_suffix": template_suffix,
                    "gift_card": gift_card,
                    "deleted_at": None,
                },
            )
            products_touched += 1

            tag_objs: list[Tag] = []
            if tags_str:
                for raw in re.split(r"[,;]", tags_str):
                    name = raw.strip()
                    if not name:
                        continue
                    tag, t_created = Tag.objects.get_or_create(name=name[:100])
                    tag_objs.append(tag)
                    if t_created:
                        tags_created += 1
            if tag_objs:
                product.tags.set(tag_objs)

            if download_images:
                img_url = _clean(meta.get("Product image URL"))
                if img_url:
                    cf = download_image(img_url, handle)
                    if cf:
                        product.featured_image.save(cf.name, cf, save=True)

            ProductVariant.objects.filter(product=product).delete()
            ProductOption.objects.filter(product=product).delete()

            option_order: list[str] = []
            seen_names: set[str] = set()
            for row in rows:
                for name, _ in iter_option_pairs(row):
                    if name not in seen_names:
                        seen_names.add(name)
                        option_order.append(name)

            option_defs: dict[str, ProductOption] = {}
            for name in option_order:
                option_defs[name] = ProductOption.objects.create(
                    product=product,
                    name=name[:100],
                )

            value_cache: dict[tuple[int, str], ProductOptionValue] = {}

            def get_option_value(opt: ProductOption, val: str) -> ProductOptionValue:
                key = (opt.id, val[:100])
                if key not in value_cache:
                    value_cache[key] = ProductOptionValue.objects.create(
                        option=opt,
                        value=val[:100],
                    )
                return value_cache[key]

            used_skus: set[str] = set()
            for row in rows:
                price = _decimal(row.get("Price"))
                if price is None:
                    continue

                option_pairs = iter_option_pairs(row)
                sku = _clean(row.get("SKU"))
                if not sku:
                    sku = _derive_variant_sku_base(handle, option_pairs)
                sku = _allocate_unique_sku(sku, used_skus)
                used_skus.add(sku)

                compare = _decimal(row.get("Compare-at price"))
                cost = _decimal(row.get("Cost per item"))
                inv = _int(row.get("Inventory quantity"), 0)
                grams = _decimal(row.get("Weight value (grams)"))
                weight = grams if grams is not None else Decimal("0")
                barcode = _clean(row.get("Barcode")) or None

                option_value_objs: list[ProductOptionValue] = []
                titles: list[str] = []
                for opt_name, opt_val in iter_option_pairs(row):
                    opt = option_defs[opt_name]
                    option_value_objs.append(get_option_value(opt, opt_val))
                    titles.append(opt_val)

                variant_title = " / ".join(titles) if titles else sku[:255]

                variant = ProductVariant.objects.create(
                    product=product,
                    title=variant_title[:255],
                    sku=sku[:100],
                    barcode=barcode[:100] if barcode else None,
                    price=price,
                    compare_at_price=compare,
                    cost_per_item=cost,
                    inventory_quantity=max(0, inv),
                    weight=weight,
                    is_active=True,
                )
                variant.option_values.set(option_value_objs)

                if download_images:
                    v_img = _clean(row.get("Variant image URL")) or _clean(
                        row.get("Product image URL")
                    )
                    if v_img:
                        cf = download_image(v_img, sku)
                        if cf:
                            variant.image.save(cf.name, cf, save=True)

                variants_created += 1

    return {
        "product_handles": products_touched,
        "variants_created": variants_created,
        "collections_created": collections_created,
        "tags_created": tags_created,
        "groups": len(groups),
    }


def load_bundled_demo_shopify_csvs(
    fixtures_dir: str | Path,
    *,
    download_images: bool = True,
    log: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """Import each file in SHOPIFY_DEMO_PRODUCT_CSV_FILENAMES that exists under fixtures_dir."""
    fixtures_dir = Path(fixtures_dir)
    acc = {
        "product_handles": 0,
        "variants_created": 0,
        "collections_created": 0,
        "tags_created": 0,
        "groups": 0,
    }
    for name in SHOPIFY_DEMO_PRODUCT_CSV_FILENAMES:
        path = fixtures_dir / name
        if not path.is_file():
            continue
        st = load_shopify_product_csv(
            path,
            download_images=download_images,
            log=log,
        )
        for k in acc:
            acc[k] += st[k]
    return acc
