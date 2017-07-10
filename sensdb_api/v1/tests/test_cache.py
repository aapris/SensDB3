from unittest import skipIf
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from django.core.cache import cache
from django.conf import settings
from model_mommy import mommy


cache_backend = settings.CACHES['default']['BACKEND']


@skipIf(cache_backend == 'django.core.cache.backends.dummy.DummyCache',
        "dummy cache in use, can't run cache tests")
class CacheTests(APITestCase):
    # would be better to test everything separately but this will do for now

    def _get_results(self, url):
        return self.client.get(url).data['results']

    def tearDown(self):
        cache.clear()

    def test_datalogger_list(self):
        url = reverse("v2:datalogger-list")
        user = mommy.make("User")
        another_user = mommy.make("User")

        self.client.force_authenticate(user=user)
        mommy.make_recipe("data.active_datalogger", user=user)
        self.assertEqual(len(self._get_results(url)), 1)

        # should be cached
        mommy.make_recipe("data.active_datalogger", user=user)
        self.assertEqual(len(self._get_results(url)), 1)

        cache.clear()
        self.assertEqual(len(self._get_results(url)), 2)

        # the other user should not see cached results
        self.client.force_authenticate(user=another_user)
        self.assertEqual(len(self._get_results(url)), 0)
