from django.urls import path

from . import views

app_name = 'tracking'

urlpatterns = [
    path('', views.stats, name='stats'),
    path('trackers/', views.tracker_profile_list, name='tracker_profiles'),
    path('trackers/new/', views.tracker_profile_create, name='tracker_profile_create'),
    path('trackers/<int:pk>/edit/', views.tracker_profile_update, name='tracker_profile_update'),
    path('trackers/<int:pk>/delete/', views.tracker_profile_delete, name='tracker_profile_delete'),
]
