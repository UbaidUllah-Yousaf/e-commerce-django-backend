"""Custom dj-rest-auth registration: Shopify-style signup with email only (username derived)."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from dj_rest_auth.registration.serializers import RegisterSerializer as BaseRegisterSerializer

UserModel = get_user_model()


class ShopifyRegisterSerializer(BaseRegisterSerializer):
    """
    Public API accepts ``email``, ``password1``, ``password2`` only.
    ``username`` is optional; defaults to trimmed email within Django limits.
    """

    username = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = dict(attrs)
        raw_uname = (attrs.get('username') or '').strip()
        email = attrs.get('email')
        attrs['username'] = (raw_uname or email)[: UserModel._meta.get_field('username').max_length]
        return super().validate(attrs)
