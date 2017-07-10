from __future__ import absolute_import

from celery import task
from django.core import management


@task(name='tasks.process_dataposts_task')
def process_dataposts_task(pk):
    management.call_command('process_dataposts', verbosity=0, pk=pk)
