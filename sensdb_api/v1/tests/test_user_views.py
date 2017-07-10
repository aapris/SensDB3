from __future__ import absolute_import
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from model_mommy import mommy
from data.models import DataloggerUser
from .utils import testserver_reverse, disable_cache


User = get_user_model()


@disable_cache()
class UserViewTests(APITestCase):
    url = reverse("v2:user-list")

    def _create_and_authenticated_admin(self):
        admin = User.objects.create_superuser(username="foo",
                password="foo", email="foo@bar.com", is_active=True)
        self.client.force_authenticate(user=admin)
        return admin

    def test_no_perms(self):
        user = User.objects.create_user(username="foo",
                password="foo", email="foo@bar.com", is_active=True)
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_staff(self):
        self._create_and_authenticated_admin()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_response(self):
        self._create_and_authenticated_admin()
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        user = results[0]
        self.assertEqual(user["url"], testserver_reverse("v2:user-detail",
                                                         args=["foo"]))
        self.assertEqual(user["username"], "foo")
        self.assertEqual(user["email"], "foo@bar.com")
        self.assertEqual(user["is_staff"], True)
        self.assertEqual(user["is_active"], True)
        self.assertEqual(user["last_login"], None)
        self.assertNotIn("related_dataloggers", user)

    def test_related_dataloggers(self):
        admin = self._create_and_authenticated_admin()
        logger = mommy.make_recipe("data.active_datalogger")
        DataloggerUser.objects.create(user=admin, datalogger=logger,
                                      role="superduperadmin")

        response = self.client.get(self.url)
        self.assertNotIn("related_dataloggers", response.data["results"][0])

        url = self.url + "?show_related_dataloggers=true"
        response = self.client.get(url)
        results = response.data["results"]
        user = results[0]
        self.assertIn("related_dataloggers", user)
        related_dataloggers = user["related_dataloggers"]
        self.assertEqual(len(related_dataloggers), 1)
        related_logger = related_dataloggers[0]
        self.assertEqual(
            related_logger["datalogger"],
            testserver_reverse("v2:datalogger-detail", args=[logger.idcode])
        )
        self.assertEqual(related_logger["role"], "superduperadmin")

    def test_username_with_special_characters(self):
        user = User.objects.create_superuser(username="foo.bar",
                password="foo", email="foo@bar.com", is_active=True)
        self.client.force_authenticate(user=user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["username"], "foo.bar")
