from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated

from ecommerce.filters import CustomerAddressFilter
from ecommerce.models.customer import CustomerAddress, CustomerProfile
from ecommerce.serializers.customer import CustomerAddressSerializer, CustomerProfileSerializer


class CustomerProfileMeView(generics.RetrieveUpdateAPIView):
    """
    Current authenticated customer (Shopify Customer–style).

    GET/PATCH ``/api/v1/customers/me/``
    """

    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = CustomerProfile.objects.select_related("user").get_or_create(
            user=self.request.user
        )
        return profile


class CustomerAddressViewSet(viewsets.ModelViewSet):
    """
    CRUD saved addresses for the authenticated customer.

    ``/api/v1/customers/me/addresses/`` — list, create
    ``/api/v1/customers/me/addresses/{id}/`` — retrieve, update, destroy
    """

    serializer_class = CustomerAddressSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options", "put", "patch", "delete"]
    filterset_class = CustomerAddressFilter
    ordering_fields = ("city", "country_code", "zip", "created_at", "updated_at", "id")

    def get_queryset(self):
        return CustomerAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        qs = self.get_queryset()
        if qs.count() == 1:
            addr = qs.first()
            if not addr.is_default_shipping and not addr.is_default_billing:
                addr.is_default_shipping = True
                addr.is_default_billing = True
                addr.save()
