from django.contrib import admin

from .models import Article, ArticleGroup, Category, Vertical


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
    list_display = ('id', 'name', 'geo', 'vertical', 'owner', 'team', 'created_at')
    list_filter = ('geo', 'vertical', 'team')
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    autocomplete_fields = ('owner', 'team', 'vertical')


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'article_type', 'status', 'country', 'language', 'vertical', 'owner', 'team', 'created_at')
    list_filter = ('article_type', 'status', 'category', 'country', 'language', 'vertical', 'groups', 'team')
    search_fields = ('title', 'slug', 'external_url', 'public_id', 'tags')
    prepopulated_fields = {'slug': ('title',)}
    autocomplete_fields = ('owner', 'team', 'category', 'vertical', 'groups')
