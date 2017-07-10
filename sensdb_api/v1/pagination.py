from collections import OrderedDict
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPagination(PageNumberPagination):
    """
    A pagination class on steroids:
    - allows addition of custom fields during initialization
    """
    def __init__(self, *custom_fields, **kwargs):
        self.page_size = kwargs.get("page_size", None)
        super(CustomPagination, self).__init__()  # just in case
        self.custom_fields = custom_fields

    def get_paginated_response(self, data):
        fields = [
            ('count', self.page.paginator.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
        ]
        if self.custom_fields:
            fields.extend(self.custom_fields)
        fields.append(
            ('results', data)
        )
        return Response(OrderedDict(fields))
