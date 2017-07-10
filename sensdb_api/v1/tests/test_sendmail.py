from __future__ import absolute_import
import mock
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from model_mommy import mommy


@mock.patch("drfapi.v2.serializers.send_datalogger_email")
class SendmailTests(APITestCase):
    url = reverse("v2:sendmail")

    def test_insufficient_permissions(self, unused_mock):
        user = mommy.make("auth.User", is_staff=False)
        mommy.make_recipe("data.active_datalogger", user=user)
        self.client.force_authenticate(user=user)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 403)

    def test_staff_permissions_work(self, unused_mock):
        user = mommy.make("auth.User", is_staff=True)
        self.client.force_authenticate(user=user)
        response = self.client.post(self.url, {})
        self.assertNotEqual(response.status_code, 403)

    def test_emails_sent(self, mocked_email_task):
        user = mommy.make("auth.User", is_staff=True)
        self.client.force_authenticate(user=user)
        logger1 = mommy.make_recipe("data.active_datalogger", user=user)
        logger2 = mommy.make_recipe("data.active_datalogger")
        response = self.client.post(self.url, {
            "dataloggers": [logger1.idcode, logger2.idcode],
            "subject": "Foo",
            "message": "Bar",
            "send_owner": True,
            "send_alertemail": True,
        })
        self.assertEqual(response.status_code, 201)
        # A task created for each logger
        self.assertEqual(mocked_email_task.delay.call_count, 2)
        actual_calls = sorted(mocked_email_task.delay.call_args_list)
        expected_calls = sorted([
            mock.call(
                idcode=logger1.idcode,
                subject="Foo",
                message="Bar",
                send_owner=True,
                send_alertemail=True,
            ),
            mock.call(
                idcode=logger2.idcode,
                subject="Foo",
                message="Bar",
                send_owner=True,
                send_alertemail=True,
            ),
        ])
        self.assertEqual(actual_calls, expected_calls)
