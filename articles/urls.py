from django.urls import path

from . import views

app_name = 'articles'

urlpatterns = [
    path('', views.article_list, name='list'),
    path('new/', views.article_create, name='create'),
    path('bulk/', views.article_bulk_action, name='bulk_action'),
    path('groups/', views.article_group_list, name='group_list'),
    path('groups/<int:pk>/edit/', views.article_group_update, name='group_update'),
    path('groups/<int:pk>/toggle-status/', views.article_group_toggle_status, name='group_toggle_status'),
    path('groups/<int:pk>/delete/', views.article_group_delete, name='group_delete'),
    path('<int:pk>/edit/', views.article_update, name='update'),
    path('<int:pk>/toggle-status/', views.article_toggle_status, name='toggle_status'),
    path('<int:pk>/delete/', views.article_delete, name='delete'),
    path('<int:pk>/banners/pin/', views.article_pin_banner, name='pin_banner'),
    path('<int:pk>/preview/', views.article_preview, name='preview'),
    path('<int:pk>/create-banner/', views.article_create_banner, name='create_banner'),
    path('a/<uuid:public_id>/', views.public_article, name='public'),
]
