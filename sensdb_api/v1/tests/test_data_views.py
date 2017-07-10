from __future__ import absolute_import
from datetime import datetime, timedelta
from urllib import urlencode
from django.utils.timezone import utc
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from model_mommy import mommy
from data.models import Data, Organization
from .utils import testserver_reverse, disable_cache


@disable_cache()
class DataListTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")
        self.unit = mommy.make_recipe("data.active_unit",
                                      datalogger=self.datalogger)

    url_name = "v2:data-list"

    @property
    def url(self):
        return reverse(self.url_name)

    def test_get_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units (or data). This is subject to change
        # XXX: should valid=True be a default filter?
        self.datalogger.user = self.user
        self.datalogger.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_viewer(self):
        self.datalogger.viewers.add(self.user)
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_admin(self):
        self.datalogger.admins.add(self.user)
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_staff(self):
        self.user.is_staff = True
        self.user.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_no_permissions(self):
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_inactive_unit(self):
        self.datalogger.admins.add(self.user)
        self.unit.active = False
        self.unit.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def _get_filtered_results(self, **filter_kwargs):
        url = "%s?%s" % (self.url, urlencode(filter_kwargs))
        response = self.client.get(url)
        return response.data["results"]

    def test_filter_timestamp(self):
        def make_data(t):
            return mommy.make("Data", unit=self.unit, timestamp=t)

        self.datalogger.admins.add(self.user)
        base_time = datetime(2016, 1, 2, 13, 37, tzinfo=utc)
        data1 = make_data(base_time)
        data2 = make_data(base_time + timedelta(days=1))
        data3 = make_data(base_time + timedelta(days=2))
        data4 = make_data(base_time + timedelta(days=3))

        # Base case
        results = self._get_filtered_results()
        self.assertEqual(len(results), 4)

        # Filter start
        start = base_time + timedelta(hours=2)
        results = self._get_filtered_results(start=start.isoformat())
        self.assertEqual(len(results), 3)
        ids = [r["id"] for r in results]
        self.assertEqual(ids, [data4.id, data3.id, data2.id])

        results = self._get_filtered_results(start=data3.timestamp.isoformat())
        self.assertEqual(len(results), 2)
        ids = [r["id"] for r in results]
        self.assertEqual(ids, [data4.id, data3.id])

        # Filter End
        results = self._get_filtered_results(end=data3.timestamp.isoformat())
        self.assertEqual(len(results), 3)
        ids = [r["id"] for r in results]
        self.assertEqual(ids, [data3.id, data2.id, data1.id])

        # Filter Both
        results = self._get_filtered_results(start=data2.timestamp.isoformat(),
                                             end=data3.timestamp.isoformat())
        self.assertEqual(len(results), 2)
        ids = [r["id"] for r in results]
        self.assertEqual(ids, [data3.id, data2.id])

    def test_filter_valid(self):
        self.datalogger.admins.add(self.user)
        first_timestamp = datetime(2016, 4, 8, 13, 33, 37, 123456, tzinfo=utc)
        data_valid = mommy.make("Data", unit=self.unit, valid=True,
                                timestamp=first_timestamp)
        data_invalid = mommy.make("Data", unit=self.unit, valid=False,
                                  timestamp=first_timestamp + timedelta(days=1))

        # Base case -- only valid data should be shown
        results = self._get_filtered_results()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], data_valid.id)

        # Filters
        results = self._get_filtered_results(show_invalid="true")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], data_invalid.id)
        self.assertEqual(results[1]["id"], data_valid.id)

    def test_filter_unit_ids(self):
        self.datalogger.admins.add(self.user)
        unit1 = self.unit
        unit2 = mommy.make_recipe("data.active_unit", datalogger=self.datalogger)
        unit3 = mommy.make_recipe("data.active_unit", datalogger=self.datalogger)
        first_timestamp = datetime(2016, 4, 8, 13, 33, 37, 123456, tzinfo=utc)
        data1 = mommy.make("Data", unit=unit1, valid=True,
                           timestamp=first_timestamp)
        data2 = mommy.make("Data", unit=unit2, valid=True,
                           timestamp=first_timestamp + timedelta(days=1))
        data3 = mommy.make("Data", unit=unit3, valid=True,
                           timestamp=first_timestamp + timedelta(days=2))
        data4 = mommy.make("Data", unit=unit3, valid=True,
                           timestamp=first_timestamp + timedelta(days=3))

        # Base case
        results = self._get_filtered_results()
        self.assertEqual(len(results), 4, "sanity check failed")

        # Filters
        unit_ids = "%s" % unit2.id
        results = self._get_filtered_results(unit_ids=unit_ids)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], data2.id)

        unit_ids = "%s,%s" % (unit1.id, unit3.id)
        results = self._get_filtered_results(unit_ids=unit_ids)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["id"], data4.id)
        self.assertEqual(results[1]["id"], data3.id)
        self.assertEqual(results[2]["id"], data1.id)

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_no_data(self):
        self.datalogger.admins.add(self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_multiple_data(self):
        self.datalogger.admins.add(self.user)
        mommy.make("Data", unit=self.unit, valid=True)
        mommy.make("Data", unit=self.unit, valid=True)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

    def test_get_multiple_unit_data(self):
        self.datalogger.admins.add(self.user)
        mommy.make("Data", unit=self.unit, valid=True)
        another_unit = mommy.make("Unit", datalogger=self.datalogger,
                                  uniquename="snowflake")
        mommy.make("Data", unit=another_unit, valid=True)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 2)

    def test_get_metadata(self):
        self.datalogger.viewers.add(self.user)
        mommy.make("Data", unit=self.unit, valid=True)
        response = self.client.get(self.url)
        data = response.data
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["next"], None)
        self.assertEqual(data["previous"], None)
        self.assertEqual(len(data["results"]), 1)

    def test_get_visible_fields(self):
        self.datalogger.viewers.add(self.user)
        mommy.make("Data", unit=self.unit, valid=True)
        self._test_visible_field_names("id value timestamp unit")

    def test_page_size(self):
        self.datalogger.viewers.add(self.user)
        for _ in range(1001):
            mommy.make("Data", unit=self.unit, valid=True)
        response = self.client.get(self.url)
        data = response.data
        self.assertEqual(data["count"], 1001)
        next_url = testserver_reverse(self.url_name) + "?page=2"
        self.assertEqual(data["next"], next_url)
        self.assertEqual(data["previous"], None)
        self.assertEqual(len(data["results"]), 1000)

    def _post_valid_data(self):
        return self.client.post(self.url,  {
            "value": "13.37",
            "timestamp": "2016-04-08T13:33:37.123456+00:00",
            "unit": reverse("v2:unit-detail", args=[self.unit.id]),
        })

    def test_post_viewer(self):
        self.datalogger.viewers.add(self.user)
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["unit"], [u"Permission denied for unit"])

    def test_post_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units (or data). This is subject to change.
        self.datalogger.user = self.user
        self.datalogger.save()
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 400)

    def test_post_admin(self):
        self.datalogger.admins.add(self.user)
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 201)

    def test_post_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["unit"], [u"Permission denied for unit"])

    def test_post_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 201)

    def test_post_created_object(self):
        self.datalogger.admins.add(self.user)
        response = self._post_valid_data()
        self.assertEqual(Data.objects.count(), 1)
        data = Data.objects.first()
        expected_timestamp = datetime(2016, 4, 8, 13, 33, 37, 123456, tzinfo=utc)
        self.assertEqual(data.timestamp, expected_timestamp)
        self.assertAlmostEqual(data.value, 13.37)
        self.assertEqual(data.unit, self.unit)

    def test_post_admin_invalid_data(self):
        self.datalogger.admins.add(self.user)
        response = self.client.post(self.url,  {})
        self.assertEqual(response.status_code, 400)

    def test_post_admin_read_only_unit(self):
        self.unit.api_read_only = True
        self.unit.save()
        self.datalogger.admins.add(self.user)
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["unit"], [u"Unit is read only"])

    def test_post_staff(self):
        self.user.is_staff = True
        self.user.save()
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 201)

    def test_post_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 400)

    def test_post_inactive_unit(self):
        self.datalogger.admins.add(self.user)
        self.unit.active = False
        self.unit.save()
        response = self._post_valid_data()
        self.assertEqual(response.status_code, 400)

    def _test_visible_field_names(self, expected_fields_str):
        self.assertEqual(Data.objects.count(), 1,
                         "precondition failed, *one* Data must exist")
        expected_field_names = {s.strip()
                                for s in expected_fields_str.split()
                                if s.strip()}
        data = self._get_single_data()
        field_names = set(data.keys())
        self.assertEqual(field_names, expected_field_names)

    def _get_single_data(self):
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1, "postcondition failed")
        data = results[0]
        return data
