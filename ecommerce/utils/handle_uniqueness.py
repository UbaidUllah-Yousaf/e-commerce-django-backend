"""Unique slug handles among non–soft-deleted rows (partial unique constraints)."""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


def unique_active_handle(
    model_class: type[models.Model],
    *,
    raw_handle: str,
    raw_title: str,
    exclude_pk: int | None = None,
    max_length: int = 50,
) -> str:
    """
    Return a ``handle`` unique among rows with ``deleted_at IS NULL``.

    - Starts from ``slugify(raw_handle)`` or ``slugify(raw_title)``.
    - If that slug is empty, uses ``item-<8 hex>``.
    - On collision, appends ``-YYYYMMDDhhmmss-<4 hex>`` (trimming base as needed).
    """
    base = slugify((raw_handle or "").strip())
    if not base:
        base = slugify((raw_title or "").strip())
    if not base:
        base = f"item-{uuid.uuid4().hex[:8]}"
    base = base[:max_length]

    candidate = base
    for _ in range(500):
        qs = model_class.all_objects.filter(deleted_at__isnull=True, handle=candidate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        ts = timezone.now().strftime("%Y%m%d%H%M%S")
        suffix = f"-{ts}-{uuid.uuid4().hex[:4]}"
        trim = max_length - len(suffix)
        if trim < 1:
            candidate = suffix[-max_length:]
        else:
            candidate = (base[:trim] + suffix)[:max_length]

    return (base[:32] + f"-{uuid.uuid4().hex}")[:max_length]
