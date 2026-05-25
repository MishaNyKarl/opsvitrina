from django.contrib import admin

from .models import Banner, BannerGroup, BannerPlacement, CreativeHeadline, CreativeImage


@admin.register(BannerGroup)
class BannerGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'status', 'owner', 'team', 'created_at')
    list_filter = ('slot', 'status', 'team')
    search_fields = ('name', 'description')
    autocomplete_fields = ('owner', 'team', 'articles', 'article_groups')


@admin.register(CreativeImage)
class CreativeImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'original_name', 'owner', 'created_at')
    list_filter = ('group', 'team')
    search_fields = ('original_name', 'group__name')
    autocomplete_fields = ('owner', 'team', 'group')


@admin.register(CreativeHeadline)
class CreativeHeadlineAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'text', 'owner', 'created_at')
    list_filter = ('group', 'team')
    search_fields = ('text', 'group__name')
    autocomplete_fields = ('owner', 'team', 'group')


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'headline', 'status', 'display_tier', 'priority', 'impressions', 'clicks', 'ctr', 'owner', 'created_at')
    list_filter = ('status', 'display_tier', 'group', 'team')
    search_fields = ('headline__text', 'utm_key', 'target_url')
    autocomplete_fields = ('owner', 'team', 'group', 'image', 'headline')


@admin.register(BannerPlacement)
class BannerPlacementAdmin(admin.ModelAdmin):
    list_display = ('id', 'banner', 'article', 'article_group', 'slot', 'display_tier', 'is_active', 'owner', 'created_at')
    list_filter = ('slot', 'display_tier', 'is_active', 'team')
    search_fields = ('banner__headline__text', 'article__title', 'article_group__name')
    autocomplete_fields = ('owner', 'team', 'banner', 'article', 'article_group')
