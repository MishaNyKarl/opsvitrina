from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Team, User


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Витрина', {'fields': ('role', 'team')}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ('Витрина', {'fields': ('role', 'team')}),
    )
    list_display = ('username', 'email', 'role', 'team', 'is_staff', 'is_active')
    list_filter = DjangoUserAdmin.list_filter + ('role', 'team')
