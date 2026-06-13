import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from logistics.mock.backend import create_mock_order, get_mock_order


@method_decorator(csrf_exempt, name="dispatch")
class MockQuiqupOAuthView(View):
    def post(self, request, *args, **kwargs):
        return JsonResponse(
            {"access_token": "mock-access-token", "token_type": "Bearer", "expires_in": 3600}
        )


@method_decorator(csrf_exempt, name="dispatch")
class MockQuiqupCreateOrderView(View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "invalid_json"}, status=400)
        return JsonResponse(create_mock_order(payload), status=201)


@method_decorator(csrf_exempt, name="dispatch")
class MockQuiqupOrderDetailView(View):
    def get(self, request, order_id, *args, **kwargs):
        try:
            return JsonResponse(get_mock_order(order_id))
        except KeyError:
            return JsonResponse({"error": "not_found"}, status=404)
