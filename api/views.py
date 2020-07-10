import json

import requests

from django.views import View
from django.http import JsonResponse


class IndexView(View):

    def get(self, request, *args, **kwargs):
        print("GET")
        data = request.GET
        result = requests.get("http://parser:8080", data)

        return JsonResponse(json.loads(result._content))
