"""DEBUG-only reference UI for order detail (line fulfillment + shipments)."""

from django.conf import settings
from django.http import Http404
from django.views.generic import TemplateView


class DemoOrderDetailView(TemplateView):
    template_name = "ecommerce/demo_order_detail.html"

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["order_pk"] = kwargs["pk"]
        return ctx
