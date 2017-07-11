from django.contrib import admin
from .models import Datalogger, UnitType, Organization, Unit, Datapost


class OrganizationAdmin(admin.ModelAdmin):
    search_fields = ('name', )
    list_display = ('name', 'created', )
    ordering = ('name', )

admin.site.register(Organization, OrganizationAdmin)


class DataloggerAdmin(admin.ModelAdmin):
    search_fields = ('name', 'idcode', )
    list_display = ('idcode', 'name', 'created', )
    ordering = ('name', 'idcode', 'created', )

admin.site.register(Datalogger, DataloggerAdmin)


class DatapostAdmin(admin.ModelAdmin):
    search_fields = ('idcode', )
    list_display = ('idcode', 'created', )
    ordering = ('created', )

admin.site.register(Datapost, DatapostAdmin)


class UnitTypeAdmin(admin.ModelAdmin):
    search_fields = ('name', 'description', 'symbol', )
    list_display = ('name', 'description', 'symbol', )
    ordering = ('name', 'symbol', 'created', )

admin.site.register(UnitType, UnitTypeAdmin)


class UnitAdmin(admin.ModelAdmin):
    search_fields = ('name', 'comment', 'symbol', )
    list_display = ('datalogger', 'unittype', 'name', 'comment', 'symbol', 'created', )
    ordering = ('datalogger', 'name', 'comment', 'symbol', 'created', )

admin.site.register(Unit, UnitAdmin)
