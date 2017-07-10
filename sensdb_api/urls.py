"""
Include all API versions, which are in use.
"""

from django.conf import settings
from django.conf.urls import url, include

urlpatterns = [
    url(r'^v1/', include('sensdb_api.v1.urls', namespace='v1')),
]
