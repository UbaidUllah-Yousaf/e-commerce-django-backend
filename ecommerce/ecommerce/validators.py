"""Shared validation rules for public-facing identifiers (codes, etc.)."""

from django.core.validators import MinLengthValidator

# All string identifiers (e.g. discount codes, gift card codes) must be at least this many characters.
MIN_IDENTIFIER_LENGTH = 6

identifier_min_length_validator = MinLengthValidator(
    MIN_IDENTIFIER_LENGTH,
    message=f"Identifier must be at least {MIN_IDENTIFIER_LENGTH} characters.",
)
