# TODO: this is at the time of writing not used anywhere and should be dropped
# from the code base if no further use cases can be found.
from rest_framework.relations import HyperlinkedIdentityField
from rest_framework.reverse import reverse


class ParameterizedHyperlinkedIdentityField(HyperlinkedIdentityField):
    """
    A version of HyperlinkedIdentityField that works with multiple kwargs in
    the URL (e.g. /foo/<foo_id>/bar/<bar_id>/baz/).
    Needed to represent nested some nested routes.

    lookup_fields is a tuple of tuples of the form:
        ('model_field', 'url_parameter')

    source: http://stackoverflow.com/questions/29362142/
    """
    lookup_fields = (('pk', 'pk'),)

    def __init__(self, *args, **kwargs):
        self.lookup_fields = kwargs.pop('lookup_fields', self.lookup_fields)
        super(ParameterizedHyperlinkedIdentityField, self).__init__(
                *args, **kwargs)

    def get_url(self, obj, view_name, request, format):
        """
        Given an object, return the URL that hyperlinks to the object.

        May raise a `NoReverseMatch` if the `view_name` and `lookup_field`
        attributes are not configured to correctly match the URL conf.
        """
        kwargs = {}
        for model_field, url_param in self.lookup_fields:
            attr = obj
            for field in model_field.split('.'):
                attr = getattr(attr, field)
            kwargs[url_param] = attr

        return reverse(view_name, kwargs=kwargs,
                       request=request, format=format)
