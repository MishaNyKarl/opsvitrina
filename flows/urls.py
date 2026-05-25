from django.urls import path

from . import views

app_name = 'flows'

urlpatterns = [
    path('', views.flow_list, name='list'),
    path('new/', views.flow_create, name='create'),
    path('<int:pk>/edit/', views.flow_update, name='update'),
]
