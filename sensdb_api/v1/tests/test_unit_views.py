from __future__ import absolute_import
from datetime import datetime, timedelta
from urllib import urlencode
from django.utils.timezone import utc
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from model_mommy import mommy
from data.models import Unit, Data, Organization
from .utils import testserver_reverse, disable_cache


# TODO: visible fields should be different for viewer, admin and staff of the
# Unit's Datalogger. Also maybe in list resource.
VISIBLE_FIELDS = """
    id
    url
    data
    datalogger
    uniquename
    name
    comment
    symbol
    min
    max
    api_read_only
    """


@disable_cache()
class UnitListTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")

    @property
    def url(self):
        return reverse("v2:unit-list")

    def test_get_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units. This is subject to change
        self.datalogger.user = self.user
        self.datalogger.save()
        self._test_visible_units(everyone=False, admins=False, nobody=False)

    def test_get_viewer(self):
        self.datalogger.viewers.add(self.user)
        self._test_visible_units(everyone=True, admins=False, nobody=False)

    def test_get_admin(self):
        self.datalogger.admins.add(self.user)
        self._test_visible_units(everyone=True, admins=True, nobody=False)

    def test_get_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        self._test_visible_units(everyone=True, admins=False, nobody=False)

    def test_get_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        self._test_visible_units(everyone=True, admins=True, nobody=False)

    def test_get_staff(self):
        self.user.is_staff = True
        self.user.save()
        self._test_visible_units(everyone=True, admins=True, nobody=False)

    def test_get_no_permissions(self):
        mommy.make_recipe("data.active_unit", datalogger=self.datalogger)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()
        mommy.make_recipe("data.active_unit", datalogger=self.datalogger)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_inactive_unit(self):
        self.datalogger.admins.add(self.user)
        mommy.make_recipe("data.active_unit", active=False,
                          datalogger=self.datalogger)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_no_units(self):
        self.datalogger.admins.add(self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_no_datalogger_units(self):
        self.datalogger.admins.add(self.user)
        another_datalogger = mommy.make("Datalogger")
        mommy.make("Unit", datalogger=another_datalogger)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_hyperlinked_fields(self):
        self.datalogger.viewers.add(self.user)
        unit = unit = mommy.make_recipe("data.active_unit",
                                 datalogger=self.datalogger,
                                 visibility='E')
        data = self._get_single_unit_data()
        self.assertEqual(
            data["datalogger"],
            testserver_reverse("v2:datalogger-detail",
                               args=[self.datalogger.idcode])
        )
        self.assertEqual(
            data["data"],
            testserver_reverse("v2:unit-data", args=[unit.id])
        )

    def test_visible_fields(self):
        self.datalogger.viewers.add(self.user)
        mommy.make_recipe("data.active_unit", datalogger=self.datalogger,
                          visibility='E')
        self._test_visible_field_names(VISIBLE_FIELDS)

    def _test_visible_units(self, everyone=False, admins=False, nobody=False):
        # TODO: duplication (e.g. with
        # test_datalogger_views.DataloggerUnitsTests)
        unit_everyone = mommy.make_recipe("data.active_unit",
                                          datalogger=self.datalogger,
                                          visibility='E')
        unit_admins = mommy.make_recipe("data.active_unit",
                                        datalogger=self.datalogger,
                                        visibility='A')
        unit_nobody = mommy.make_recipe("data.active_unit",
                                        datalogger=self.datalogger,
                                        visibility='N')

        num_visible = sum([everyone, admins, nobody])

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        results = response.data["results"]
        self.assertEqual(len(results), num_visible)
        names = {r["uniquename"] for r in results}

        if everyone:
            self.assertIn(unit_everyone.uniquename, names)
        else:
            self.assertNotIn(unit_everyone.uniquename, names)
        if admins:
            self.assertIn(unit_admins.uniquename, names)
        else:
            self.assertNotIn(unit_admins.uniquename, names)
        if nobody:
            self.assertIn(unit_nobody.uniquename, names)
        else:
            self.assertNotIn(unit_nobody.uniquename, names)

    def _test_visible_field_names(self, expected_fields_str):
        self.assertEqual(Unit.objects.count(), 1,
                         "precondition failed, *one* Unit must exist")
        expected_field_names = {s.strip()
                                for s in expected_fields_str.split()
                                if s.strip()}
        data = self._get_single_unit_data()
        field_names = set(data.keys())
        self.assertEqual(field_names, expected_field_names)

    def _get_single_unit_data(self):
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1, "postcondition failed")
        data = results[0]
        return data


@disable_cache()
class UnitDetailTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")
        self.unit = mommy.make_recipe("data.active_unit",
                                      datalogger=self.datalogger)

    url_name = "v2:unit-detail"

    @property
    def url(self):
        return reverse(self.url_name, args=[self.unit.id])

    def test_get_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units. This is subject to change
        self.datalogger.user = self.user
        self.datalogger.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_viewer(self):
        self.datalogger.viewers.add(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.unit.id)

    def test_get_admin(self):
        self.datalogger.admins.add(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.unit.id)

    def test_get_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.unit.id)

    def test_get_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.unit.id)

    def test_get_staff(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.unit.id)

    def test_get_no_permissions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_inactive_unit(self):
        self.datalogger.admins.add(self.user)
        self.unit.active = False
        self.unit.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_not_found(self):
        self.unit.delete()
        url = reverse(self.url_name, args=[self.datalogger.id, 404])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_get_another_datalogger_unit(self):
        another_datalogger = mommy.make("Datalogger")
        another_unit = mommy.make("Unit", datalogger=another_datalogger)
        url = reverse(self.url_name,
                      args=[self.datalogger.id, another_unit.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_visible_fields(self):
        self.datalogger.viewers.add(self.user)
        self._test_visible_field_names(VISIBLE_FIELDS)

    def test_delete(self):
        # DELETE not yet implemented
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 405)

    def _test_visible_field_names(self, expected_fields_str):
        # TODO: duplication with Datalogger detail tests, but maybe that
        # doesn't matter?
        response = self.client.get(self.url)
        field_names = set(response.data.keys())
        expected_field_names = {s.strip()
                                for s in expected_fields_str.split()
                                if s.strip()}
        self.assertEqual(field_names, expected_field_names)


@disable_cache()
class UnitDataTests(APITestCase):
    # TODO: loads of duplication with DataListTests

    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")
        self.unit = mommy.make_recipe("data.active_unit",
                                      datalogger=self.datalogger)

    url_name = "v2:unit-data"

    @property
    def url(self):
        return reverse(self.url_name, args=[self.unit.id])

    def test_get_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units (or data). This is subject to change
        # XXX: should valid=True be a default filter?
        self.datalogger.user = self.user
        self.datalogger.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

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
        self.assertEqual(response.status_code, 404)

    def test_get_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_inactive_unit(self):
        self.datalogger.admins.add(self.user)
        self.unit.active = False
        self.unit.save()
        mommy.make("Data", unit=self.unit)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def _get_filtered_results(self, **filter_kwargs):
        url = "%s?%s" % (self.url, urlencode(filter_kwargs))
        response = self.client.get(url)
        return response.data["results"]

    def test_filter_timestamp(self):
        # TODO: duplicate test method
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
        # TODO: duplicate test method
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

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_no_data(self):
        self.datalogger.admins.add(self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_no_unit_data(self):
        self.datalogger.admins.add(self.user)
        another_unit = mommy.make("Unit", datalogger=self.datalogger,
                                  uniquename="snowflake")
        mommy.make("Data", unit=another_unit)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_metadata(self):
        self.datalogger.viewers.add(self.user)
        mommy.make("Data", unit=self.unit, valid=True)
        response = self.client.get(self.url)
        data = response.data
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["next"], None)
        self.assertEqual(data["previous"], None)
        self.assertEqual(len(data["results"]), 1)
        unit_url = testserver_reverse("v2:unit-detail",
                                      args=[self.unit.id])
        self.assertEqual(data["unit"], unit_url)

    def test_get_visible_fields(self):
        self.datalogger.viewers.add(self.user)
        mommy.make("Data", unit=self.unit, valid=True)
        # TODO: unit should not be visible here
        self._test_visible_field_names("id value timestamp unit")

    def test_page_size(self):
        self.datalogger.viewers.add(self.user)
        for _ in range(1001):
            mommy.make("Data", unit=self.unit, valid=True)
        response = self.client.get(self.url)
        data = response.data
        self.assertEqual(data["count"], 1001)
        next_url = (testserver_reverse(self.url_name, args=[self.unit.id]) +
                    "?page=2")
        self.assertEqual(data["next"], next_url)
        self.assertEqual(data["previous"], None)
        self.assertEqual(len(data["results"]), 1000)

    def test_post(self):
        # POST must be done on /data endpoint, not /units/ID/data
        self.datalogger.admins.add(self.user)
        response = self.client.post(self.url,  {
            "value": "13.37",
            "timestamp": "2016-04-08T13:33:37.123456+00:00"
        })
        self.assertEqual(response.status_code, 405)

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


@disable_cache()
class UnitCreateTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")

    @property
    def url(self):
        return reverse("v2:unit-list")

    def _make_post_request(self, extra_data=None):
        data = {
            "uniquename": "my-unique-snowflake",
            "datalogger": reverse("v2:datalogger-detail",
                                  args=[self.datalogger.idcode]),
        }
        if extra_data:
            data.update(extra_data)
        return self.client.post(self.url, data)

    def test_post_viewer(self):
        self.datalogger.viewers.add(self.user)

        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["datalogger"],
            [u"Permission to edit Datalogger denied"]
        )

    def test_post_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units. This is subject to change
        self.datalogger.user = self.user
        self.datalogger.save()

        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

    def test_post_admin(self):
        self.datalogger.admins.add(self.user)

        response = self._make_post_request()
        self.assertEqual(response.status_code, 201)

    def test_post_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()

        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

    def test_post_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()

        response = self._make_post_request()
        self.assertEqual(response.status_code, 201)

    def test_post_admin_created_object(self):
        self.datalogger.admins.add(self.user)

        self._make_post_request({
            "name": "my lovely unit",
            "min": 3.0,
        })

        self.assertEqual(Unit.objects.count(), 1)
        unit = Unit.objects.first()
        # Units created through the api have api_read_only=False by default
        self.assertFalse(unit.api_read_only)

        self.assertEqual(unit.uniquename, "my-unique-snowflake")
        self.assertEqual(unit.datalogger, self.datalogger)
        self.assertEqual(unit.name, "my lovely unit")
        self.assertAlmostEqual(unit.min, 3.0)

    def test_post_admin_invalid_uniquename(self):
        mommy.make_recipe("data.active_unit", uniquename="my-unique-snowflake",
                          datalogger=self.datalogger)
        self.datalogger.admins.add(self.user)

        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

    def test_post_staff(self):
        self.user.is_staff = True
        self.user.save()

        response = self._make_post_request()
        self.assertEqual(response.status_code, 201)

    def test_post_no_permissions(self):
        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

    def test_post_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()

        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

    def test_post_nonexistent_datalogger(self):
        self.datalogger.delete()

        response = self._make_post_request()
        self.assertEqual(response.status_code, 400)

    def test_post_unauthenticated(self):
        self.client.force_authenticate(user=None)

        response = self._make_post_request()
        self.assertEqual(response.status_code, 401)


@disable_cache()
class UnitUpdateTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")
        self.unit = mommy.make_recipe("data.active_unit",
                                      datalogger=self.datalogger,
                                      uniquename="my-unique-snowflake")

    url_name = "v2:unit-detail"

    @property
    def url(self):
        return reverse(self.url_name, args=[self.unit.id])

    def _make_put_request(self, extra_data=None):
        data = {
            "uniquename": "my-unique-snowflake",
            "datalogger": reverse("v2:datalogger-detail",
                                  args=[self.datalogger.idcode]),
        }
        if extra_data:
            data.update(extra_data)
        return self.client.put(self.url, data)

    def test_put_viewer(self):
        self.datalogger.viewers.add(self.user)

        response = self._make_put_request()
        self.assertEqual(response.status_code, 400)

    def test_put_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units. This is subject to change
        self.datalogger.user = self.user
        self.datalogger.save()

        response = self._make_put_request()
        self.assertEqual(response.status_code, 404)

    def test_put_admin(self):
        self.datalogger.admins.add(self.user)

        response = self._make_put_request()
        self.assertEqual(response.status_code, 200)

    def test_put_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()

        response = self._make_put_request()
        self.assertEqual(response.status_code, 400)

    def test_put_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()

        response = self._make_put_request()
        self.assertEqual(response.status_code, 200)

    def test_put_admin_updated_object(self):
        self.datalogger.admins.add(self.user)

        self._make_put_request({
            "name": "my lovely unit",
            "min": 3.0,
            "api_read_only": True,  # should be ignored
        })

        self.assertEqual(Unit.objects.count(), 1)
        unit = Unit.objects.first()

        self.assertEqual(unit.uniquename, "my-unique-snowflake")
        self.assertEqual(unit.datalogger, self.datalogger)
        self.assertEqual(unit.name, "my lovely unit")
        self.assertAlmostEqual(unit.min, 3.0)
        self.assertEqual(unit.api_read_only, False)

    def test_put_admin_disallowed_fields(self):
        self.datalogger.admins.add(self.user)
        another_datalogger = mommy.make_recipe("data.active_datalogger")
        another_datalogger.admins.add(self.user)

        response = self._make_put_request({
            "uniquename": "new-uniquename",
            "datalogger": reverse("v2:datalogger-detail",
                                  args=[another_datalogger.idcode]),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["uniquename"],
            ["Editing the field 'uniquename' not allowed"]
        )
        self.assertEqual(
            response.data["datalogger"],
            ["Editing the field 'datalogger' not allowed"]
        )

    def test_put_admin_read_only_unit(self):
        self.unit.api_read_only = True
        self.unit.save()
        self.datalogger.admins.add(self.user)

        response = self._make_put_request()
        self.assertEqual(response.status_code, 405)

    def test_put_admin_unit_missing(self):
        self.datalogger.admins.add(self.user)
        self.unit.delete()

        response = self._make_put_request()
        self.assertEqual(response.status_code, 404)

    def test_put_staff(self):
        self.user.is_staff = True
        self.user.save()

        response = self._make_put_request()
        self.assertEqual(response.status_code, 200)

    def test_put_no_permissions(self):
        response = self._make_put_request()
        self.assertEqual(response.status_code, 404)

    def test_put_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()

        response = self._make_put_request()
        self.assertEqual(response.status_code, 404)

    def test_put_unauthenticated(self):
        self.client.force_authenticate(user=None)

        response = self._make_put_request()
        self.assertEqual(response.status_code, 401)


@disable_cache()
class UnitPartialUpdateTests(APITestCase):
    # TODO: this has sooooo much duplication with UnitUpdateTests

    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")
        self.unit = mommy.make_recipe("data.active_unit",
                                      datalogger=self.datalogger,
                                      uniquename="my-unique-snowflake")

    url_name = "v2:unit-detail"

    @property
    def url(self):
        return reverse(self.url_name, args=[self.unit.id])

    def _make_patch_request(self, extra_data=None):
        data = extra_data or {}
        return self.client.patch(self.url, data)

    def test_patch_viewer(self):
        self.datalogger.viewers.add(self.user)

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 403)

    def test_patch_owner(self):
        # XXX: for now on, a dataloggers owner has no permissions on the
        # logger's units. This is subject to change
        self.datalogger.user = self.user
        self.datalogger.save()

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 404)

    def test_patch_admin(self):
        self.datalogger.admins.add(self.user)

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 200)

    def test_patch_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 403)

    def test_patch_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        self.datalogger.organization = organization
        self.datalogger.save()

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 200)

    def test_patch_admin_updated_object(self):
        self.datalogger.admins.add(self.user)

        self._make_patch_request({
            "name": "my lovely unit",
            "min": 3.0,
            "api_read_only": True,  # should be ignored
        })

        self.assertEqual(Unit.objects.count(), 1)
        unit = Unit.objects.first()

        self.assertEqual(unit.uniquename, "my-unique-snowflake")
        self.assertEqual(unit.datalogger, self.datalogger)
        self.assertEqual(unit.name, "my lovely unit")
        self.assertAlmostEqual(unit.min, 3.0)
        self.assertEqual(unit.api_read_only, False)

    def test_patch_admin_disallowed_fields(self):
        self.datalogger.admins.add(self.user)
        another_datalogger = mommy.make_recipe("data.active_datalogger")
        another_datalogger.admins.add(self.user)

        response = self._make_patch_request({
            "uniquename": "new-uniquename",
            "datalogger": reverse("v2:datalogger-detail",
                                  args=[another_datalogger.idcode]),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["uniquename"],
            ["Editing the field 'uniquename' not allowed"]
        )
        self.assertEqual(
            response.data["datalogger"],
            ["Editing the field 'datalogger' not allowed"]
        )

    def test_patch_admin_read_only_unit(self):
        self.unit.api_read_only = True
        self.unit.save()
        self.datalogger.admins.add(self.user)

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 405)

    def test_patch_admin_unit_missing(self):
        self.datalogger.admins.add(self.user)
        self.unit.delete()

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 404)

    def test_patch_staff(self):
        self.user.is_staff = True
        self.user.save()

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 200)

    def test_patch_no_permissions(self):
        response = self._make_patch_request()
        self.assertEqual(response.status_code, 404)

    def test_patch_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 404)

    def test_patch_unauthenticated(self):
        self.client.force_authenticate(user=None)

        response = self._make_patch_request()
        self.assertEqual(response.status_code, 401)
