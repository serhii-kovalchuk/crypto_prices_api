import json

import requests

from django.views import View
from django.http import JsonResponse


class IndexView(View):

    def get(self, request, *args, **kwargs):
        result = requests.get("http://parser:8080", request.GET)

        return JsonResponse(json.loads(result._content))

