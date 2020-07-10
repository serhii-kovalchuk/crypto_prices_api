from django.urls import path
from api.views import IndexView


app_name = 'api'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
]
