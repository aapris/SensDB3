from __future__ import absolute_import, unicode_literals, print_function
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, MethodNotAllowed
from rest_framework.reverse import reverse
from sensdb3.permissions import can_edit
from sensdb3 import models


User = get_user_model()


# TODO: see if HyperlinkedModelSerializer could be used and refer to users etc
# with hyperlinks


class GenericValidationMixin(object):
    """A mixin that provides some validation helpers for serializers"""
    def validate_field_not_changed(self, field_name, value):
        if self.instance:
            old_value = getattr(self.instance, field_name)
            if old_value != value:
                raise serializers.ValidationError(
                    _("Editing the field '%s' not allowed" % field_name)
                )
        return value

    def get_request_or_die(self):
        try:
            return self.context["request"]
        except KeyError:
            msg = ("creating or updating instances with {} requires "
                   "request in serializer context"
                   ).format(self.__class__.__name__)
            raise ValueError(msg)


class RelatedDataloggerValidationMixin(GenericValidationMixin):
    """A mixin for implementing datalogger validation for models that have a
    relation to Datalogger.

    In general, when POSTing these models, user permissions have to be checked
    against the datalogger. Also, when updating (PUTing or PATCHing), it has to
    be made sure that the datalogger has not been changed"""

    def validate_datalogger(self, value):
        # This is called automatically per DRF's validation rules
        request = self.get_request_or_die()

        self.validate_field_not_changed("datalogger", value)

        if not can_edit(request.user, value):
            raise serializers.ValidationError(
                _("Permission to edit Datalogger denied")
            )
        return value


class DataloggerSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v2:datalogger-detail',
        lookup_field='idcode',
        lookup_url_kwarg='idcode',
        read_only=True
    )
    units = serializers.HyperlinkedIdentityField(
        view_name='v2:datalogger-units',
        lookup_field='idcode',
        read_only=True
    )
    formulas = serializers.HyperlinkedIdentityField(
        view_name='v2:datalogger-formulas',
        lookup_field='idcode',
        read_only=True
    )


    class Meta:
        model = models.Datalogger
        fields = (
            "id", "url", "units", "formulas", "uid", "idcode", "customcode",
            "status", "name", "description", "measuringinterval",
            "transmissioninterval", "timezone", "in_utc", "active", "lat",
            "lon", "firstmeasuring", "lastmeasuring",
            "measuringcount", "datapostcount", "lastdatapost",
        )

    def to_representation(self, instance):
        ret = super(DataloggerSerializer, self).to_representation(instance)

        request = self.context["request"]
        if can_edit(request.user, instance):
            ret["admins"] = self._serialize_users(instance.all_admins)
            ret["viewers"] = self._serialize_users(instance.all_viewers)
            ret["related_users"] = self._serialize_related_users(instance)
        return ret

    def _serialize_users(self, qs):
        return [
            {
                "username": u.username
            }
            for u in qs
        ]

    def _serialize_related_users(self, datalogger):
        qs = models.DataloggerUser.objects.filter(datalogger=datalogger)
        return [
            {
                "username": d.user.username,
                "role": d.role,
            }
            for d in qs
        ]


class UnitSerializer(RelatedDataloggerValidationMixin,
                     serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v2:unit-detail',
        read_only=True
    )
    data = serializers.HyperlinkedIdentityField(
        view_name='v2:unit-data',
        read_only=True
    )
    datalogger = serializers.HyperlinkedRelatedField(
        view_name='v2:datalogger-detail',
        queryset=models.Datalogger.objects.all(),
        lookup_field="idcode",
    )

    class Meta:
        model = models.Unit
        fields = (
            "id", "url", "data", "datalogger", "uniquename", "name", "comment",
            "symbol", "min", "max", "api_read_only",
        )
        extra_kwargs = {
            'api_read_only': {
                'default': False,
                'read_only': True,
            }
        }

    def update(self, instance, validated_data):
        request = self.get_request_or_die()
        if not can_edit(request.user, instance, check_api_read_only=False):
            # This branch is only entered when doing a PATCH request (partial
            # update), because datalogger validation is done first.
            raise PermissionDenied(_("Permission to edit Unit denied"))
        elif instance.api_read_only:
            raise MethodNotAllowed(request.method, _("Unit is read only"))
        return super(UnitSerializer, self).update(instance, validated_data)

    def validate_uniquename(self, value):
        return self.validate_field_not_changed("uniquename", value)


class FormulaSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v2:formula-detail',
        read_only=True
    )
    datalogger = serializers.HyperlinkedRelatedField(
        view_name='v2:datalogger-detail',
        queryset=models.Datalogger.objects.all(),
        lookup_field="idcode",
    )

    class Meta:
        model = models.Formula
        fields = (
            "id", "url", "datalogger", "name", "comment",
            "symbol", "min", "max",
        )


class DataSerializer(serializers.ModelSerializer):
    # XXX: these are left here as commented-out code, as they (or at least
    # Datapost) are likely needed in the future
    # The reason we use a custom relation is that the default ChoiceField
    # widget has too many options and causes serious performance impacts.
    # We should probably use a hyperlink instead of a primary key though
    #measuring = serializers.PrimaryKeyRelatedField(
    #    queryset=models.Measuring.objects.all(),
    #    style={'base_template': 'input.html'}
    #)
    #datapost = serializers.PrimaryKeyRelatedField(
    #    queryset=models.Datapost.objects.all(),
    #    style={'base_template': 'input.html'}
    #)
    unit = serializers.HyperlinkedRelatedField(
        view_name='v2:unit-detail',
        queryset=models.Unit.objects.all()
    )

    class Meta:
        model = models.Data
        fields = ("id", "value", "timestamp", "unit")

    def validate_unit(self, value):
        try:
            request = self.context["request"]
        except KeyError:
            raise ValueError(
                "creating or updating instances with DataSerializer requires "
                "request in serializer context"
            )

        if not can_edit(request.user, value, check_api_read_only=False):
            raise serializers.ValidationError(_("Permission denied for unit"))
        elif value.api_read_only:
            raise serializers.ValidationError(_("Unit is read only"))
        return value


class LogSerializer(RelatedDataloggerValidationMixin,
                    serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v2:log-detail',
        read_only=True
    )
    datalogger = serializers.HyperlinkedRelatedField(
        view_name='v2:datalogger-detail',
        queryset=models.Datalogger.objects.all(),
        lookup_field="idcode",
    )

    def create(self, validated_data):
        request = self.get_request_or_die()
        validated_data['user'] = request.user
        return super(LogSerializer, self).create(validated_data)

    class Meta:
        model = models.Dataloggerlog
        fields = (
            'id',
            'url',
            'datalogger',
            'user',
            'type',
            'action',
            'target',
            'title',
            'text',
            'starttime',
            'endtime',
            'showongraph',
        )
        read_only_fields = (
            'id',
            'url',
            'user',
            'type',
            'action',
            'target',
        )


class UserSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='v2:user-detail',
        lookup_field='username',
        read_only=True
    )

    class Meta:
        model = User
        fields = (
            'url',
            'username',
            'email',
            'is_staff',
            'is_active',
            'last_login',
        )

    def to_representation(self, instance):
        ret = super(UserSerializer, self).to_representation(instance)
        show_related_dataloggers = self.context.get("show_related_dataloggers",
                                                    False)
        if show_related_dataloggers:
            related_dataloggers = self._get_related_dataloggers(instance)
            ret["related_dataloggers"] = related_dataloggers
        return ret

    def _get_related_dataloggers(self, user):
        qs = user.dataloggeruser_set.all()
        return [
            {
                "datalogger": reverse(
                    "v2:datalogger-detail",
                    args=[d.datalogger.idcode],
                    request=self.context["request"],
                ),
                "role": d.role,
            }
            for d in qs
        ]


class SendmailSerializer(serializers.Serializer):
    # dataloggers by idcode
    dataloggers = serializers.ListField(
        child=serializers.CharField()
    )
    subject = serializers.CharField()
    message = serializers.CharField()
    send_owner = serializers.BooleanField()
    send_alertemail = serializers.BooleanField()

    def validate_dataloggers(self, idcodes):
        unique_idcodes = set(idcodes)
        if not unique_idcodes:
            raise serializers.ValidationError(
                _("At least one datalogger required"))
        loggers = models.Datalogger.objects.filter(idcode__in=unique_idcodes)
        found_idcodes = set(logger.idcode for logger in loggers)
        not_found_idcodes = unique_idcodes - found_idcodes
        if not_found_idcodes:
            msg = _("Dataloggers %s not found") % ", ".join(not_found_idcodes)
            raise serializers.ValidationError(msg)
        # Return Dataloggers, not idcodes
        return loggers

    def save(self):
        data = self.validated_data
        for datalogger in data["dataloggers"]:
            send_datalogger_email.delay(
                idcode=datalogger.idcode,
                subject=data["subject"],
                message=data["message"],
                send_owner=data["send_owner"],
                send_alertemail=data["send_alertemail"],
            )
