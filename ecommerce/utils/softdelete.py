"""Soft-delete helpers: default manager hides rows with deleted_at set."""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self) -> tuple[int, dict[str, int]]:
        """Set deleted_at on all rows in this queryset (bulk soft delete)."""
        now = timezone.now()
        count = self.update(deleted_at=now)
        return count, {self.model._meta.label: count}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Permanently remove rows from the database."""
        return super().delete()

    def restore(self) -> int:
        """Clear deleted_at for all rows in this queryset."""
        return self.update(deleted_at=None)


class SoftDeleteManager(models.Manager):
    """Excludes soft-deleted rows (deleted_at IS NULL)."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class SoftDeleteAllManager(models.Manager):
    """Includes soft-deleted rows; use for imports, admin, and hard wipes."""

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """Abstract base with deleted_at, soft delete(), and restore()."""

    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True

    def delete(
        self,
        using=None,
        keep_parents=False,
        hard=False,
    ):
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
        return 1, {self._meta.label: 1}

    def restore(self) -> None:
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])
