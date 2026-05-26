"""
URL configuration for opsvitrina project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path

from articles.views import article_behavior_event, public_article, public_article_group, public_article_next_feed
from core.views import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('a/<uuid:public_id>/events/', article_behavior_event, name='article_behavior_event'),
    path('a/<uuid:public_id>/next/', public_article_next_feed, name='public_article_next_feed'),
    path('a/<uuid:public_id>/', public_article, name='public_article'),
    path('g/<uuid:public_id>/', public_article_group, name='public_article_group'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('articles/', include('articles.urls')),
    path('banners/', include('banners.urls')),
    path('flows/', include('flows.urls')),
    path('stats/', include('tracking.urls')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
