from datetime import datetime
from django.core.urlresolvers import reverse_lazy
from django.utils import timezone
from model_mommy import mommy
from rest_framework.test import APITestCase
from data.models import Datapost


STATUS_URL = reverse_lazy("v2:status")


class StatusViewTests(APITestCase):

    def setUp(self):
        self.admin = mommy.make("auth.User", is_staff=True)

    def _login_admin(self):
        self.client.force_authenticate(self.admin)

    def test_no_permissions(self):
        expected_response = {
            "error": True,
            "message": "Only for staff members",
        }
        response = self.client.get(STATUS_URL)
        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(response.content, expected_response)

        self.client.force_authenticate(mommy.make("auth.User", is_staff=False))
        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(response.content, expected_response)

    def test_empty(self):
        self._login_admin()
        response = self.client.get(STATUS_URL)
        self.assertJSONEqual(response.content, {
            "latest_datapost": None,
            "latest_processed_datapost": None,
        })

    def test_datapost(self):
        self._login_admin()
        datapost = Datapost.objects.create(idcode="foo")
        datapost.created = datetime(2017, 1, 2, 13, 37).replace(
                tzinfo=timezone.utc)
        datapost.save()

        response = self.client.get(STATUS_URL)
        self.assertJSONEqual(response.content, {
            "latest_datapost": {
                "created": "2017-01-02T13:37:00Z",
                "idcode": "foo",
            },
            "latest_processed_datapost": None,
        })

    def test_processed_datapost(self):
        self._login_admin()
        datapost = Datapost.objects.create(idcode="foo", status=1)
        datapost.created = datetime(2017, 1, 2, 13, 37).replace(
                tzinfo=timezone.utc)
        datapost.save()

        response = self.client.get(STATUS_URL)
        self.assertJSONEqual(response.content, {
            "latest_datapost": {
                "created": "2017-01-02T13:37:00Z",
                "idcode": "foo",
            },
            "latest_processed_datapost": {
                "created": "2017-01-02T13:37:00Z",
                "idcode": "foo",
            },
        })
