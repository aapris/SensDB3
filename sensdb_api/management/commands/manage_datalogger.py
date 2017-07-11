# -*- coding: utf-8 -*-

import re
from django.core.management.base import BaseCommand, CommandError
from sensdb3.models import Datalogger

import logging
log = logging.getLogger('datapost')


def check_idcode(idcode):
    if idcode is None or idcode == '':
        raise CommandError('A valid idcode for Datalogger is mandatory. Hint: use --idcode <valid_idcode> argument.')


def check_datalogger_exists(idcode):
    try:
        dl = Datalogger.objects.get(idcode=idcode)
    except Datalogger.DoesNotExist:
        raise CommandError('A Datalogger with idcode "{}" does not exist.'.format(idcode))
    return dl


def activate_datalogger(dl):
    dl.status = 'ACTIVE'
    dl.active = True
    dl.save()


def deactivate_datalogger(dl):
    dl.status = 'INACTIVE'
    dl.active = False
    dl.save()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('command', nargs=1, type=str)

        parser.add_argument('--idcode',
                            action='store',
                            dest='idcode',
                            default=None,
                            help=u'Handle only dataposts of "idcode"')

        parser.add_argument('--activate',
                            action='store_true',
                            help=u'Handle only dataposts of "idcode"')

    args = ''
    help = 'Processes Dataposts'
    commands = ['create', 'destroy', 'activate', 'list']

    def handle(self, *args, **options):
        command = options.get('command')[0]
        idcode = options.get('idcode')
        activate = options.get('activate')
        # List all dataloggers
        if command.lower() == 'list':
            pattern = '{:<20} {:<9} {}'
            self.stdout.write(self.style.SUCCESS(pattern.format('Idcode', 'Status', 'Created')))
            for dl in Datalogger.objects.order_by('idcode'):
                self.stdout.write(pattern.format(dl.idcode, dl.status, dl.created))
        # Create a datalogger
        if command.lower() == 'create':
            check_idcode(idcode)
            dl, created = Datalogger.objects.get_or_create(idcode=idcode)
            if created == False:
                raise CommandError('Datalogger with idcode "{}" already exists.'.format(idcode))
            if activate:
                activate_datalogger(dl)
            self.stdout.write(self.style.SUCCESS('Datalogger was created successfully.'))
        if command.lower() == 'activate':
            dl = check_datalogger_exists(idcode)
            if dl.active == True:
                self.stdout.write(self.style.WARNING('Datalogger was already active.'))
            else:
                activate_datalogger(dl)
                self.stdout.write(self.style.SUCCESS('Datalogger was activated successfully.'))
        if command.lower() == 'deactivate':
            dl = check_datalogger_exists(idcode)
            if dl.active == False:
                self.stdout.write(self.style.WARNING('Datalogger was already inactive.'))
            else:
                deactivate_datalogger(dl)
                self.stdout.write(self.style.SUCCESS('Datalogger was deactivated successfully.'))
        if command.lower() == 'show':
            dl = check_datalogger_exists(idcode)
            self.stdout.write('''
Idcode:  {} 
Status:  {}
Created: {}
'''.format(dl.idcode, dl.status, dl.created))
        if command.lower() == 'destroy':
            dl = check_datalogger_exists(idcode)
            if dl.active == True:
                self.stdout.write(self.style.ERROR('Deactivate Datalogger before destroying it permanently.'))
            else:
                dl.delete()
                self.stdout.write(self.style.SUCCESS('Datalogger was destroyed permanently and all data is forever gone.'))

