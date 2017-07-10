from functools import wraps
from rest_framework.reverse import reverse
from django.core import cache as cache_module
from mock import patch


def testserver_reverse(url_name, *args, **kwargs):
    return "http://testserver%s" % reverse(url_name, *args, **kwargs)


class TestContextDecorator(object):
    def enable(self):
        raise NotImplementedError()

    def disable(self):
        raise NotImplementedError()

    def __enter__(self):
        self.enable()

    def __exit__(self, exc_type, exc_value, traceback):
        self.disable()

    def __call__(self, test_func):
        if isinstance(test_func, type):
            cls = test_func
            decorated_setUp = cls.setUp
            decorated_tearDown = cls.tearDown

            def setUp(inner_self):
                self.enable()
                decorated_setUp(inner_self)

            def tearDown(inner_self):
                decorated_tearDown(inner_self)
                self.disable()

            cls.setUp = setUp
            cls.tearDown = tearDown
            return cls
        else:
            @wraps(test_func)
            def inner(*args, **kwargs):
                with self:
                    return test_func(*args, **kwargs)


class disable_cache(TestContextDecorator):
    def enable(self):
        # Just patch default cache to always find nothing
        # since drf-extensions stores the instance of the cache everywhere,
        # which makes it impossible to replace with DummyCache
        def mocked_cache_get(key, default=None, version=None):
            return default
        self.patch = patch.object(cache_module.cache, 'get', mocked_cache_get)
        self.patch.start()

    def disable(self):
        self.patch.stop()
