from django.db import models

from utils.handle_uniqueness import unique_active_handle
from utils.softdelete import SoftDeleteModel
from utils.timestamped import TimeStampedModel


class Collection(SoftDeleteModel, TimeStampedModel):
    title = models.CharField(max_length=255)
    handle = models.SlugField(blank=True)
    description = models.TextField(blank=True)

    image = models.ImageField(
        upload_to="collections/",
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["handle"],
                condition=models.Q(deleted_at__isnull=True),
                name="ecommerce_collection_unique_handle_active",
            ),
        ]

    def save(self, *args, **kwargs):
        handle_max = self._meta.get_field("handle").max_length or 50
        self.handle = unique_active_handle(
            Collection,
            raw_handle=self.handle or "",
            raw_title=self.title or "",
            exclude_pk=self.pk,
            max_length=handle_max,
        )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
