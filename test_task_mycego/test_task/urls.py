from django.urls import path
from . import views

urlpatterns = [
    path('', views.authorize, name='authorize'),
    path('callback/', views.callback, name='callback'),
    path('files/', views.files, name='files'),
    path('download/<path:file_path>/', views.download, name='download'),
    path('index/', views.index, name='index'),
]
