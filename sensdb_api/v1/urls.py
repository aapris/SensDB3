from __future__ import absolute_import, unicode_literals, print_function
from django.conf.urls import url
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views as auth_token_views
from . import views


router = DefaultRouter()
router.register(r'dataloggers', views.DataloggerViewSet,
                base_name="datalogger")
router.register(r'units', views.UnitViewSet, base_name="unit")
router.register(r'formulas', views.FormulaViewSet, base_name="formula")
router.register(r'data', views.DataViewSet, base_name="data")
router.register(r'logs', views.LogViewSet, base_name="log")
router.register(r'users', views.UserViewSet, base_name="user")


urlpatterns = router.urls


urlpatterns += [
    url(r'^export/$', views.export_data, name="export-data"),
    url(r'^sendmail/$', views.Sendmail.as_view({"post": "create"}),
        name="sendmail"),
    url(r'^status/$', views.status, name="status"),
    url(r'^auth/$', auth_token_views.obtain_auth_token, name="auth"),
]
