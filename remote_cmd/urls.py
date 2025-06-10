from django.urls import path, include
from remote_cmd import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generate-exe/', views.generate_exe, name='generate_exe'),
    path('download-exe/', views.download_exe, name='download_exe'),
    path('cmd/<str:client_id>/', views.cmd_page, name='cmd_page'),
    path('api/', include('remote_cmd.api_urls')),
]