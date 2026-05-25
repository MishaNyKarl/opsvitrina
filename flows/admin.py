from django.contrib import admin

from .models import Domain, Flow, TrafficSource


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(TrafficSource)
class TrafficSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


@admin.register(Flow)
class FlowAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', 'article', 'owner', 'team', 'traffic_source', 'created_at')
    list_filter = ('status', 'traffic_source', 'domain', 'team')
    search_fields = ('name', 'public_id', 'article__title')
    autocomplete_fields = ('owner', 'team', 'article', 'domain', 'traffic_source')
