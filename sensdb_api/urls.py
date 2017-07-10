"""
Include all API versions, which are in use.
Also define all non-REST endpoints here.
"""

from django.conf.urls import url, include
from . import views

urlpatterns = [
    url(r'^v1/', include('sensdb_api.v1.urls', namespace='v1')),
    url(r'^espeasy/?$', views.postdata_espeasy, name='postdata_espeasy'),
]
