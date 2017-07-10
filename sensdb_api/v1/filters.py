from __future__ import absolute_import, unicode_literals, print_function
from django.contrib.auth import get_user_model
import django_filters
from django_filters.filters import BaseInFilter, NumberFilter, CharFilter
from django_filters.rest_framework import FilterSet
from sensdb3 import models


User = get_user_model()


class NumberInFilter(BaseInFilter, NumberFilter):
    pass


class CharInFilter(BaseInFilter, CharFilter):
    pass


class DataFilter(FilterSet):
    start = django_filters.IsoDateTimeFilter(
        name="timestamp",
        lookup_expr="gte"
    )
    end = django_filters.IsoDateTimeFilter(
        name="timestamp",
        lookup_expr="lte"
    )
    show_invalid = django_filters.BooleanFilter(
        method="filter_show_invalid",
        widget=django_filters.widgets.BooleanWidget()
    )
    unit_ids = NumberInFilter(name="unit_id", lookup_expr="in")

    class Meta:
        model = models.Data
        fields = ["start", "end", "show_invalid", "unit"]

    def __init__(self, data=None, **kwargs):
        if data is not None and "show_invalid" not in data:
            # Hacky way to create a default value for show_invalid
            data = data.copy()  # get mutable version of the QueryDict
            data["show_invalid"] = False
        super(DataFilter, self).__init__(data=data, **kwargs)

    def filter_show_invalid(self, queryset, name, value):
        if not value:
            queryset = queryset.filter(valid=True)
        return queryset


class UserFilter(FilterSet):
    # A convenience filter for Include staff no matter what
    # The other filters say
    include_staff = django_filters.BooleanFilter(
        method="filter_include_staff",
        widget=django_filters.widgets.BooleanWidget(),
    )
    roles = CharInFilter(
        method="filter_roles",
    )

    class Meta:
        model = User
        fields = [
            "is_staff",
            "roles",
            "include_staff",  # Make sure this filter is last
        ]

    def filter_include_staff(self, qs, name, value):
        if value:
            qs = qs | User.objects.filter(is_staff=True)
        return qs

    def filter_roles(self, qs, name, value):
        # .distinct() is done in self.qs
        return qs.filter(dataloggeruser__role__in=value)

    @property
    def qs(self):
        # We have to do this here to combine include_staff with filter_roles
        parent = super(UserFilter, self).qs
        return parent.distinct().filter(is_active=True)
