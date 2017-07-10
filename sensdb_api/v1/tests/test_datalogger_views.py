from __future__ import absolute_import
from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from model_mommy import mommy
from data.models import Datalogger, Unit, Organization
from .utils import testserver_reverse, disable_cache


# TODO: visible fields should be different for viewer, admin and staff (and
# also maybe for Datalogger list resource)
VISIBLE_FIELDS = """
    id
    url
    units
    formulas
    uid
    idcode
    customcode
    status
    name
    description
    measuringinterval
    transmissioninterval
    timezone
    in_utc
    active
    lat
    lon
    image
    firstmeasuring
    lastmeasuring
    measuringcount
    datapostcount
    lastdatapost
    internal_attributes
    """

ADMIN_VISIBLE_FIELDS = VISIBLE_FIELDS + """
    admins
    viewers
    related_users
    """


DATALOGGER_UNIT_VISIBLE_FIELDS = """
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
class DataloggerListTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)

    @property
    def url(self):
        return reverse("v2:datalogger-list")

    def test_get_owner(self):
        mommy.make_recipe("data.active_datalogger", user=self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_viewer(self):
        datalogger = mommy.make_recipe("data.active_datalogger")
        datalogger.viewers.add(self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_admin(self):
        datalogger = mommy.make_recipe("data.active_datalogger")
        datalogger.admins.add(self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_staff(self):
        self.user.is_staff = True
        self.user.save()
        mommy.make_recipe("data.active_datalogger")
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        datalogger = mommy.make_recipe("data.active_datalogger",
                                       organization=organization)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        datalogger = mommy.make_recipe("data.active_datalogger",
                                       organization=organization)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1)

    def test_get_no_permissions(self):
        mommy.make_recipe("data.active_datalogger")
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_inactive(self):
        mommy.make("data.Datalogger", active=False, user=self.user)
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_no_dataloggers(self):
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(results, [])

    def test_url_field(self):
        datalogger = mommy.make_recipe("data.active_datalogger",
                                       viewers=[self.user])
        data = self._get_single_datalogger_data()
        self.assertEqual(
            data["url"],
            testserver_reverse("v2:datalogger-detail",
                               args=[datalogger.idcode])
        )

    def test_viewer_visible_fields(self):
        mommy.make_recipe("data.active_datalogger", viewers=[self.user])
        self._test_visible_field_names(VISIBLE_FIELDS)

    def test_admin_visible_fields(self):
        mommy.make_recipe("data.active_datalogger", admins=[self.user])
        self._test_visible_field_names(ADMIN_VISIBLE_FIELDS)

    def test_staff_visible_fields(self):
        self.user.is_staff = True
        self.user.save()
        mommy.make_recipe("data.active_datalogger")
        self._test_visible_field_names(ADMIN_VISIBLE_FIELDS)

    def test_admin_and_viewer_fields_multiple_loggers(self):
        logger = mommy.make_recipe("data.active_datalogger", admins=[self.user])
        another_logger = mommy.make_recipe("data.active_datalogger",
                                           admins=[mommy.make("User")],
                                           viewers=[self.user])

        response = self.client.get(self.url)
        loggers = response.data["results"]

        this = filter(lambda l: l["idcode"] == logger.idcode, loggers)[0]
        other = filter(lambda l: l["idcode"] == another_logger.idcode, loggers)[0]
        self.assertIn("admins", this)
        self.assertIn("viewers", this)
        self.assertNotIn("admins", other)
        self.assertNotIn("viewers", other)

    def test_post(self):
        # POST not yet implemented
        response = self.client.post(self.url,  {})
        self.assertEqual(response.status_code, 405)

    def _get_single_datalogger_data(self):
        response = self.client.get(self.url)
        results = response.data["results"]
        self.assertEqual(len(results), 1, "postcondition failed")
        data = results[0]
        return data

    def _test_visible_field_names(self, expected_fields_str):
        self.assertEqual(Datalogger.objects.count(), 1,
                         "precondition failed, *one* Datalogger must exist")
        expected_field_names = {s.strip()
                                for s in expected_fields_str.split()
                                if s.strip()}
        data = self._get_single_datalogger_data()
        field_names = set(data.keys())
        self.assertEqual(field_names, expected_field_names)


@disable_cache()
class DataloggerDetailTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")

    url_name = "v2:datalogger-detail"

    @property
    def url(self):
        return reverse(self.url_name, args=[self.datalogger.idcode])

    def test_get_owner(self):
        self.datalogger.user = self.user
        self.datalogger.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.datalogger.id)

    def test_get_viewer(self):
        self.datalogger.viewers.add(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.datalogger.id)

    def test_get_admin(self):
        self.datalogger.admins.add(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.datalogger.id)

    def test_get_staff(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(response.data["id"], self.datalogger.id)

    def test_get_organization_viewer(self):
        organization = mommy.make(Organization, viewers=[self.user])
        datalogger = mommy.make_recipe("data.active_datalogger",
                                       organization=organization)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_organization_admin(self):
        organization = mommy.make(Organization, admins=[self.user])
        datalogger = mommy.make_recipe("data.active_datalogger",
                                       organization=organization)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_no_permissions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_inactive(self):
        self.datalogger.active = False
        self.datalogger.save()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_unauthenticated(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_get_not_found(self):
        self.datalogger.delete()
        url = reverse(self.url_name, args=[404])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_viewer_visible_fields(self):
        self.datalogger.viewers.add(self.user)
        self._test_visible_field_names(VISIBLE_FIELDS)

    def test_admin_visible_fields(self):
        self.datalogger.admins.add(self.user)
        self._test_visible_field_names(ADMIN_VISIBLE_FIELDS)

    def test_staff_visible_fields(self):
        self.user.is_staff = True
        self.user.save()
        self._test_visible_field_names(ADMIN_VISIBLE_FIELDS)

    def test_admin_and_viewer_fields(self):
        logger_admin = self.user
        organization_admin = mommy.make("User")
        logger_viewer = mommy.make("User")
        organization_viewer = mommy.make("User")
        both_viewer = mommy.make("User")
        random_user = mommy.make("User")
        organization = mommy.make("Organization",
                                  admins=[organization_admin],
                                  viewers=[organization_viewer, both_viewer])
        self.datalogger.organization = organization
        self.datalogger.save()
        self.datalogger.admins.add(self.user)
        self.datalogger.viewers.add(logger_viewer)
        self.datalogger.viewers.add(both_viewer)

        response = self.client.get(self.url)
        self.assertIn("admins", response.data)
        self.assertIn("viewers", response.data)

        # Do a sorted comparison because we don't really care about the order here
        self.assertEqual(
            sorted(response.data["admins"]),
            sorted([
                {
                    "username": logger_admin.username
                },
                {
                    "username": organization_admin.username
                }
            ])
        )
        self.assertEqual(
            sorted(response.data["viewers"]),
            sorted([
                {
                    "username": logger_viewer.username
                },
                {
                    "username": organization_viewer.username
                },
                {
                    "username": both_viewer.username
                }
            ])
        )

    def test_related_users_field(self):
        self.datalogger.admins.add(self.user)

        mommy.make("data.DataloggerUser",
            datalogger=self.datalogger,
            user=mommy.make("auth.User", username="foo"),
            role="hyperadmin"
        )

        mommy.make("data.DataloggerUser",
            datalogger=self.datalogger,
            user=mommy.make("auth.User", username="bar"),
            role="night's watch guardian of the night"
        )

        response = self.client.get(self.url)
        self.assertIn("related_users", response.data)

        self.assertEqual(
            sorted(response.data["related_users"]),
            sorted([
                {
                    "username": "foo",
                    "role": "hyperadmin",
                },
                {
                    "username": "bar",
                    "role": "night's watch guardian of the night",
                }
            ])
        )

    def test_put(self):
        # PUT not yet implemented
        response = self.client.put(self.url,  {})
        self.assertEqual(response.status_code, 405)

    def test_delete(self):
        # DELETE not yet implemented
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 405)

    def _test_visible_field_names(self, expected_fields_str):
        response = self.client.get(self.url)
        field_names = set(response.data.keys())
        expected_field_names = {s.strip()
                                for s in expected_fields_str.split()
                                if s.strip()}
        self.assertEqual(field_names, expected_field_names)


@disable_cache()
class DataloggerUnitsTests(APITestCase):
    def setUp(self):
        self.user = mommy.make("User")
        self.client.force_authenticate(user=self.user)
        self.datalogger = mommy.make_recipe("data.active_datalogger")

    @property
    def url(self):
        return reverse("v2:datalogger-units", args=[self.datalogger.idcode])

    def test_get_owner(self):
        # XXX: for now on, a datalogger's owner has no permissions on the
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

    def test_get_inactive_datalogger(self):
        self.datalogger.admins.add(self.user)
        self.datalogger.active = False
        self.datalogger.save()
        mommy.make_recipe("data.active_unit", datalogger=self.datalogger)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

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
        unit = mommy.make_recipe("data.active_unit",
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
        self._test_visible_field_names(DATALOGGER_UNIT_VISIBLE_FIELDS)

    def test_post(self):
        # POST not implemented
        response = self.client.post(self.url,  {})
        self.assertEqual(response.status_code, 405)

    def _test_visible_units(self, everyone=False, admins=False, nobody=False):
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
