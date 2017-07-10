from __future__ import absolute_import, unicode_literals, print_function
from django.db.models import Q
from sensdb3.models import (
    Datalogger,
    Unit,
    Data,
    Formula,
    Grouplogger,
    Dataloggerlog,
)


# TODO: it would probably be wise to implement these as Manager methods in
# data.models, e.g. Datalogger.objects.for_user(user)
# TODO: possible duplicate logic with data.views.decorators


def _get_objects(Model, user, datalogger=None):
    """A generic helper for filtering datalogger-related objects based on user
    permissions"""
    if not user.is_authenticated():
        return Model.objects.none()

    if datalogger is not None:
        # This branch is a simple performance optimization
        if not can_view(user, datalogger):
            return Model.objects.none()
        objects = Model.objects.filter(datalogger=datalogger)
    else:
        objects = Model.objects.all()
        objects = objects.filter(datalogger__active=True)
        if not user.is_staff:
            objects = objects.filter(
                Q(datalogger__viewers__id=user.id) |
                Q(datalogger__admins__id=user.id) |
                Q(datalogger__organization__admins__id=user.id) |
                Q(datalogger__organization__viewers__id=user.id)
            )
            objects = objects.distinct()

    objects = objects.order_by('id')
    return objects


def get_dataloggers(user):
    # Staff will see all loggers, but regular users only loggers
    # which they are allowed to see or administrate
    if not user.is_authenticated():
        # Redundant -- permissions should handle this
        return Datalogger.objects.none()

    qs = Datalogger.objects.filter(active=True)
    qs = qs.order_by('name', 'idcode')
    if user.is_staff:
        return qs

    qs = qs.filter(
        Q(viewers__id=user.id) | Q(admins__id=user.id) | Q(user=user) |
        Q(organization__viewers__id=user.id) | Q(organization__admins__id=user.id)
    )
    qs = qs.distinct()
    return qs


def get_dataloggers_by_role(user, role):
    if not user.is_authenticated():
        return Datalogger.objects.none()
    return Datalogger.objects.filter(
        dataloggeruser__user=user,
        dataloggeruser__role=role,
    ).distinct()


def get_units(user, datalogger=None):
    if not user.is_authenticated():
        return Unit.objects.none()

    if datalogger is not None:
        units = datalogger.units.all()
        # This part does essentially the same thing as the humongous query in
        # the else branch, only we can simplify it if we're limiting the Units
        # to one datalogger
        if user.is_staff or user in datalogger.admins.all():
            units = units.filter(visibility__in=['E', 'A'])
        elif datalogger.organization and user in datalogger.organization.admins.all():
            units = units.filter(visibility__in=['E', 'A'])
        elif user in datalogger.viewers.all():
            units = units.filter(visibility='E')
        elif datalogger.organization and user in datalogger.organization.viewers.all():
            units = units.filter(visibility__in=['E'])
        else:
            units = units.none()
    else:
        units = Unit.objects.all()
        units = units.filter(datalogger__active=True)
        if user.is_staff:
            units = units.filter(visibility__in=['E', 'A'])
        else:
            # Behold, the mother of all queries!
            units = units.filter(
                (
                    (Q(datalogger__viewers__id=user.id) |
                     Q(datalogger__organization__viewers__id=user.id)) &
                    Q(visibility='E')
                ) | (
                    (Q(datalogger__admins__id=user.id) |
                     Q(datalogger__organization__admins__id=user.id)) &
                    Q(visibility__in=['E', 'A'])
                )
            )
            units = units.distinct()

    units = units.filter(active=True)
    units = units.order_by('id')
    return units


def get_formulas(user, datalogger=None):
    formulas = _get_objects(Formula, user, datalogger=datalogger)
    formulas = formulas.filter(active=True)
    return formulas


def get_logs(user, datalogger=None):
    return _get_objects(Dataloggerlog, user, datalogger=datalogger)


def get_data(user):
    units = get_units(user)
    return Data.objects.filter(unit__in=units).order_by("-timestamp")


def can_view(user, instance):
    if isinstance(instance, Datalogger):
        datalogger = instance
        active = instance.active
    elif isinstance(instance, (Unit, Formula)):
        datalogger = instance.datalogger
        active = datalogger.active and instance.active
    else:
        raise ValueError(
                "instance must be either a Datalogger, Unit or Formula")

    if not active:
        return False

    if user.is_staff:
        return True

    if datalogger.organization:
        if user in datalogger.organization.viewers.all() or \
                user in datalogger.organization.admins.all():
            return True

    if user in datalogger.viewers.all() or \
            user in datalogger.admins.all() or \
            user == datalogger.user:
        return True

    return False


def _check_valid_model(instance):
    valid_classes = (Datalogger, Grouplogger, Unit, Formula)
    if not isinstance(instance, valid_classes):
        raise ValueError("instance must be one of: " + ",".join(valid_classes))


def can_edit(user, instance, check_api_read_only=True):
    _check_valid_model(instance)

    if isinstance(instance, Datalogger):
        datalogger = instance
        editable = instance.active
    elif isinstance(instance, Grouplogger):
        datalogger = instance
        editable = instance.active
    elif isinstance(instance, Unit):
        datalogger = instance.datalogger
        editable = datalogger.active and instance.active
        if check_api_read_only:
            editable = editable and not instance.api_read_only
    elif isinstance(instance, Formula):
        return False  # TODO: logic for formulae not yet implemented
    else:
        assert False, "should not get here"

    if not editable:
        return False
    if not user.is_authenticated():
        return False

    if user.is_staff:
        return True
    if datalogger.admins.filter(id=user.id).exists():
        return True
    # datalogger might also be a Grouplogger, in which case it doesn't have an
    # Organization
    organization = getattr(datalogger, "organization", None)
    if organization and organization.admins.filter(id=user.id).exists():
        return True

    return False


def has_editable_dataloggers(user):
    dataloggers = get_dataloggers(user)
    for dl in dataloggers:
        if can_edit(user, dl):
            return True
    return False
