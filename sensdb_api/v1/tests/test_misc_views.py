from __future__ import absolute_import
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from model_mommy import mommy
from .utils import testserver_reverse


class ApiRootTests(APITestCase):
    @property
    def url(self):
        return reverse("v2:api-root")

    def test_get_authenticated(self):
        user = mommy.make("User")
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        datalogger_list_url = testserver_reverse("v2:datalogger-list")
        unit_list_url = testserver_reverse("v2:unit-list")
        formula_list_url = testserver_reverse("v2:formula-list")
        data_list_url = testserver_reverse("v2:data-list")
        log_list_url = testserver_reverse("v2:log-list")
        user_list_url = testserver_reverse("v2:user-list")
        self.assertEqual(dict(response.data), {
            "dataloggers": datalogger_list_url,
            "units": unit_list_url,
            "formulas": formula_list_url,
            "data": data_list_url,
            "logs": log_list_url,
            "users": user_list_url,
        })
