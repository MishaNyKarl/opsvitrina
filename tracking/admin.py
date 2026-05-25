from django.contrib import admin

from .models import ArticleBehaviorEvent, PostbackEvent, VisitEvent


@admin.register(ArticleBehaviorEvent)
class ArticleBehaviorEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'event_type', 'session_id', 'click_id', 'scroll_depth', 'time_on_page', 'owner', 'created_at')
    list_filter = ('event_type', 'team')
    search_fields = ('article__title', 'session_id', 'click_id', 'target_url')
    autocomplete_fields = ('owner', 'team', 'article')


@admin.register(VisitEvent)
class VisitEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_type', 'flow', 'article', 'click_id', 'owner', 'created_at')
    list_filter = ('event_type', 'team')
    search_fields = ('click_id', 'flow__name', 'article__title')
    autocomplete_fields = ('owner', 'team', 'flow', 'article')


@admin.register(PostbackEvent)
class PostbackEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'click_id', 'partner', 'status', 'payout', 'currency', 'flow', 'owner', 'created_at')
    list_filter = ('status', 'partner', 'currency', 'team')
    search_fields = ('click_id', 'partner', 'flow__name')
    autocomplete_fields = ('owner', 'team', 'flow')
