from __future__ import absolute_import, unicode_literals, print_function
from django.contrib.auth import get_user_model
from django_filters import rest_framework as filters
from rest_framework import viewsets, mixins
from rest_framework.decorators import detail_route, api_view
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.reverse import reverse
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from sensdb3.models import (Datalogger, Unit, Data, Formula, Dataloggerlog,
                         Datapost)
from sensdb3.datatools import get_formula_data
from sensdb3.permissions import (get_dataloggers, get_units, get_formulas,
                              get_data, get_logs, can_view)
from .filters import DataFilter, UserFilter
from . import serializers, pagination


DEFAULT_PAGE_SIZE = 100
DATA_PAGE_SIZE = 1000
User = get_user_model()


class BaseViewSet(CacheResponseMixin,
                  mixins.RetrieveModelMixin,
                  mixins.ListModelMixin,
                  viewsets.GenericViewSet):
    """A ViewSet that implements features and useful properties shared by most
    views of the api"""
    permission_classes = (IsAuthenticated,)

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            if hasattr(self, "get_paginator_custom_fields"):
                custom_fields = self.get_paginator_custom_fields()
            else:
                custom_fields = []
            page_size = getattr(self, "page_size", DEFAULT_PAGE_SIZE)
            self._paginator = pagination.CustomPagination(
                    *custom_fields, page_size=page_size)
        return self._paginator


class DataloggerViewSet(BaseViewSet):
    """Datalogger resource"""
    model = Datalogger
    serializer_class = serializers.DataloggerSerializer
    lookup_field = "idcode"

    def get_queryset(self):
        return get_dataloggers(self.request.user)

    @detail_route(methods=['get'])
    @cache_response()
    def units(self, request, *args, **kwargs):
        """List units for a single datalogger"""
        datalogger = self.get_object()
        qs = get_units(self.request.user, datalogger=datalogger)
        return self._get_children(datalogger, qs, serializers.UnitSerializer)

    @detail_route(methods=['get'])
    @cache_response()
    def formulas(self, request, *args, **kwargs):
        """List formulas for a single datalogger"""
        datalogger = self.get_object()
        qs = get_formulas(self.request.user, datalogger=datalogger)
        return self._get_children(
                datalogger, qs, serializers.FormulaSerializer)

    def _get_children(self, datalogger, qs, serializer_cls):
        datalogger_url = reverse(
            "v2:datalogger-detail",
            args=[datalogger.idcode],
            request=self.request
        )

        paginator = pagination.CustomPagination(
            ("datalogger", datalogger_url),
            page_size=DEFAULT_PAGE_SIZE,
        )

        qs = paginator.paginate_queryset(qs, self.request)

        # TODO: should maybe limit visible fields here
        serializer = serializer_cls(
            qs,
            many=True,
            context={"request": self.request}
        )
        return paginator.get_paginated_response(serializer.data)


class UnitViewSet(mixins.CreateModelMixin,
                  mixins.UpdateModelMixin,
                  BaseViewSet):
    """Unit resource"""
    model = Unit
    serializer_class = serializers.UnitSerializer

    def get_queryset(self):
        return get_units(self.request.user)

    @detail_route(methods=['get'])
    @cache_response()
    def data(self, request, *args, **kwargs):
        """
        List data for a single unit

        Same as /data/?unit_ids=ID
        """
        unit = self.get_object()
        unit_url = reverse(
            "v2:unit-detail",
            args=[unit.id],
            request=self.request
        )

        paginator = pagination.CustomPagination(
            ("unit", unit_url),
            page_size=DATA_PAGE_SIZE,
        )

        data = unit.data_set.order_by("-timestamp")
        filter = DataFilter(self.request.GET, queryset=data)
        data = filter.qs
        data = paginator.paginate_queryset(data, self.request)

        # TODO: should maybe limit visible fields here
        serializer = serializers.DataSerializer(
            data,
            many=True,
            context={"request": self.request}
        )
        return paginator.get_paginated_response(serializer.data)


class FormulaViewSet(BaseViewSet):
    """Formula resource"""
    model = Formula
    serializer_class = serializers.FormulaSerializer

    def get_queryset(self):
        return get_formulas(self.request.user)


class DataViewSet(mixins.CreateModelMixin,
                  BaseViewSet):
    """Data resource"""
    model = Data
    queryset = Data.objects.all().order_by("-timestamp")
    serializer_class = serializers.DataSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = DataFilter
    page_size = DATA_PAGE_SIZE

    def get_queryset(self):
        return get_data(self.request.user).order_by("-timestamp")


class LogViewSet(mixins.CreateModelMixin,
                 BaseViewSet):
    """Log resource"""
    model = Dataloggerlog
    serializer_class = serializers.LogSerializer
    filter_backends = (filters.DjangoFilterBackend,)

    def get_queryset(self):
        return get_logs(self.request.user).order_by("-starttime")


class UserViewSet(BaseViewSet):
    model = User
    serializer_class = serializers.UserSerializer
    lookup_field = "username"
    lookup_value_regex = '[^/]+'
    permission_classes = [IsAdminUser]
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = UserFilter

    def get_queryset(self):
        qs = User.objects.all()
        qs = qs.prefetch_related("dataloggeruser_set__datalogger")
        return qs

    def get_serializer_context(self):
        context = super(UserViewSet, self).get_serializer_context()
        show_related_dataloggers_param = self.request.query_params.get(
                "show_related_dataloggers", "")
        show_related_dataloggers = (
            show_related_dataloggers_param.lower()
            in ("1", "true")
        )
        context["show_related_dataloggers"] = show_related_dataloggers
        return context


class Sendmail(mixins.CreateModelMixin,
               viewsets.GenericViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = serializers.SendmailSerializer


# TODO: cache this one manually
@api_view(['GET'])
def export_data(request):
    def response_403():
        return Response({"error": "403 Forbidden"}, status=403)

    # Reuse filter questionably
    filter = DataFilter(request.GET, queryset=Data.objects.all())

    if not request.user.is_authenticated():
        return Response(
            {"error": "unauthenticated"},
            status=401
        )

    if not filter.form.is_valid():
        return Response(
            {"error": "error validating filter data"},
            status=400
        )

    filter_data = filter.form.cleaned_data
    if not filter_data["start"] or not filter_data["end"]:
        return Response(
            {"error": "specify GET params `start` and `end`"},
            status=400
        )

    results = []

    if filter_data["unit_ids"]:
        for unit in Unit.objects.filter(id__in=filter_data["unit_ids"]):
            if not can_view(request.user, unit):
                return response_403()

        results.extend(
            {
                "id": d.id,
                "value": d.value,
                "timestamp": d.timestamp,
                "formula": None,
                "unit": reverse(
                    "v2:unit-detail",
                    args=[d.unit.id],
                    request=request,
                ),
                "raw": True,
            } for d in filter.qs.prefetch_related("unit")
        )

    formula_ids = request.GET.get("formula_ids", "")
    if formula_ids:
        formula_ids = map(int, formula_ids.split(","))
        for id in formula_ids:
            formula = Formula.objects.get(id=id)
            if not can_view(request.user, formula):
                return response_403()

            records = get_formula_data(formula,
                                       filter_data["start"],
                                       filter_data["end"],
                                       showinvalid=filter_data["show_invalid"])
            formula_url = reverse(
                "v2:formula-detail",
                args=[formula.id],
                request=request,
            )
            results.extend(
                {
                    "id": None,
                    "value": r["value"],
                    "timestamp": r["timestamp"],
                    "unit": None,
                    "formula": formula_url,
                    "raw": False,
                } for r in records
            )

    results.sort(key=lambda r: r["timestamp"])

    return Response({
        "results": results,
        "count": len(results),
        "next": None,
        "previous": None,
    })


@api_view(['GET'])
def status(request):
    def serialize_datapost(datapost):
        if datapost is None:
            return None
        return {
            "created": datapost.created,
            "idcode": datapost.idcode,
        }

    if not request.user.is_staff:
        return Response({
            "error": True,
            "message": "Only for staff members"
        }, status=403)
    latest_datapost = Datapost.objects.order_by("-created").first()
    latest_processed_datapost = Datapost.objects.filter(
            status=1).order_by("-created").first()
    return Response({
        "latest_datapost": serialize_datapost(latest_datapost),
        "latest_processed_datapost": serialize_datapost(
            latest_processed_datapost),
    })
