from rest_framework import serializers
from .models import Client
from django.utils import timezone
from datetime import timedelta

class ClientSerializer(serializers.ModelSerializer):
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ['client_id', 'token', 'last_command', 'last_output', 'command_id', 'last_seen', 'is_online']

    def get_is_online(self, obj):
        if obj.last_seen:
            return timezone.now() - obj.last_seen < timedelta(seconds=10)
        return False