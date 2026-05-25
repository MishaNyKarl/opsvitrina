from django.contrib import admin

from .models import Article, ArticleGroup, ArticleGroupMembership, Category, Vertical


class ArticleGroupMembershipInline(admin.TabularInline):
    model = ArticleGroupMembership
    extra = 0
    autocomplete_fields = ('article',)
    fields = ('article', 'priority', 'utm_query', 'is_active', 'impressions')
    readonly_fields = ('impressions',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


@admin.register(Vertical)
class VerticalAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'slug')


@admin.register(ArticleGroup)
class ArticleGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'public_id', 'geo', 'vertical', 'owner', 'team', 'created_at')
    list_filter = ('geo', 'vertical', 'team')
    search_fields = ('name', 'slug', 'public_id', 'description')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('owner', 'team', 'vertical')
    inlines = (ArticleGroupMembershipInline,)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'article_type', 'status', 'country', 'language', 'vertical', 'owner', 'team', 'created_at')
    list_filter = ('article_type', 'status', 'category', 'country', 'language', 'vertical', 'groups', 'team')
    search_fields = ('title', 'slug', 'external_url', 'public_id', 'tags')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ('owner', 'team', 'category', 'vertical', 'groups')


@admin.register(ArticleGroupMembership)
class ArticleGroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'article', 'priority', 'utm_query', 'is_active', 'impressions')
    list_filter = ('is_active', 'group')
    search_fields = ('group__name', 'article__title', 'utm_query')
    autocomplete_fields = ('group', 'article')
