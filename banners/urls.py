from django.urls import path

from . import views

app_name = 'banners'

urlpatterns = [
    path('', views.banner_list, name='list'),
    path('upload/', views.banner_upload, name='upload'),
    path('groups/bulk/', views.banner_group_bulk_action, name='group_bulk_action'),
    path('groups/<int:pk>/edit/', views.banner_group_update, name='group_update'),
    path('groups/<int:pk>/toggle-status/', views.banner_group_toggle_status, name='group_toggle_status'),
    path('groups/<int:pk>/delete/', views.banner_group_delete, name='group_delete'),
    path('<int:pk>/edit/', views.banner_update, name='update'),
    path('<int:pk>/utm/', views.banner_update_utm, name='update_utm'),
    path('<int:pk>/toggle-status/', views.banner_toggle_status, name='toggle_status'),
    path('<int:pk>/delete/', views.banner_delete, name='delete'),
    path('<int:pk>/click/', views.banner_click, name='click'),
]
