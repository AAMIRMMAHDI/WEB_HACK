from django.urls import path
from remote_cmd.views import ClientRegisterView, ClientCommandView, ClientPollView

urlpatterns = [
    path('register/', ClientRegisterView.as_view(), name='register'),
    path('command/<str:client_id>/', ClientCommandView.as_view(), name='command'),
    path('poll/<str:client_id>/', ClientPollView.as_view(), name='poll'),
]
