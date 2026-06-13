from django.db import models
from utils.timestamped import TimeStampedModel


class Tag(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
