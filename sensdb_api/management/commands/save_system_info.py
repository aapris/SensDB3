# -*- coding: utf-8 -*-

from optparse import make_option
from django.core.management.base import BaseCommand


from . import system_monitor

class Command(BaseCommand):
    args = ''
    help = 'Gather system information and save it as a Datapost'

    def handle(self, *args, **options):
        try:
            verbosity = int(options.get('verbosity', 1))  # 0, 1 (default) or 2
        except ValueError:
            verbosity = 1
        data_str = system_monitor.main()
        if verbosity > 0:
            print(data_str)
