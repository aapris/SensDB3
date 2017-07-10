from __future__ import absolute_import
from datetime import timedelta
from unittest import skip
from urllib import urlencode
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse, reverse_lazy
from model_mommy import mommy
from .utils import disable_cache


@disable_cache()
class LogResourceTests(APITestCase):

    # Setup

    url = reverse_lazy("v2:log-list")

    def setUp(self):
        self.logger_admin = mommy.make("User")
        self.logger_viewer = mommy.make("User")
        self.random_dude = mommy.make("User")
        self.visible_datalogger = mommy.make_recipe(
            "data.active_datalogger",
            admins=[self.logger_admin],
            viewers=[self.logger_viewer]
        )
        self.invisible_datalogger = mommy.make_recipe("data.active_datalogger")
        self.visible_log = mommy.make(
            "Dataloggerlog",
            datalogger=self.visible_datalogger
        )
        self.invisible_log = mommy.make(
            "Dataloggerlog",
            datalogger=self.invisible_datalogger
        )

    # Tests for GET

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_admin(self):
        self.client.force_authenticate(user=self.logger_admin)
        self._assert_only_visible_log_in_results()

    def test_get_viewer(self):
        self.client.force_authenticate(user=self.logger_viewer)
        self._assert_only_visible_log_in_results()

    def test_get_no_permissions(self):
        self.client.force_authenticate(user=self.random_dude)
        self._assert_empty_results()

    @skip("not yet implemented")
    def test_filter(self):
        another_visible_datalogger = mommy.make_recipe(
            "data.active_datalogger",
            admins=[self.logger_admin],
            viewers=[self.logger_viewer]
        )
        another_visible_log = mommy.make(
            "Dataloggerlog",
            datalogger=self.visible_datalogger
        )

        self.client.force_authenticate(user=self.logger_viewer)
        self.client

    def _assert_only_visible_log_in_results(self):
        results = self._get_logs()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.visible_log.id)

    def _assert_empty_results(self):
        results = self._get_logs()
        self.assertEqual(len(results), 0)

    def _get_logs(self, **filter_kwargs):
        if filter_kwargs:
            url = "%s?%s" % (self.url, urlencode(filter_kwargs))
        else:
            url = self.url
        response = self.client.get(url)
        results = response.data["results"]
        return results

    # Tests for POST

    def test_post(self):
        self.assertEqual(self.visible_datalogger.logs.count(), 1,
                         "precondition failed, more than 1 log found")
        self.client.force_authenticate(user=self.logger_admin)
        response = self._make_post_request()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.visible_datalogger.logs.count(), 2)
        log = self.visible_datalogger.logs.exclude(
                id=self.visible_log.id).get()
        self.assertEqual(log.user, self.logger_admin)

    def test_post_no_datalogger_permissions(self):
        self.client.force_authenticate(user=self.logger_admin)

        no_perms_datalogger = self.invisible_datalogger
        response = self._make_post_request({
            "datalogger": reverse("v2:datalogger-detail",
                                  args=[no_perms_datalogger.idcode]),
        })

        self.assertEqual(response.status_code, 400)
        # No new logs created
        self.assertEqual(self.visible_datalogger.logs.count(), 1)
        self.assertEqual(self.invisible_datalogger.logs.count(), 1)

    def test_post_viewer(self):
        self.client.force_authenticate(user=self.logger_viewer)
        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

        self.client.force_authenticate(user=self.random_dude)
        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

        self.assertEqual(self.visible_datalogger.logs.count(), 1)

    def _make_post_request(self, extra_data=None):
        start = timezone.now()
        data = {
            "datalogger": reverse("v2:datalogger-detail",
                                  args=[self.visible_datalogger.idcode]),
            'title': 'snowflake',
            'text': 'some logging data',
            'starttime': start,
            'endtime': start + timedelta(hours=3),
            'showongraph': True,
        }
        if extra_data:
            data.update(extra_data)
        return self.client.post(self.url, data)
