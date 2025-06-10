from django.db import models
import uuid

class Client(models.Model):
    client_id = models.CharField(max_length=255, unique=True)
    token = models.CharField(max_length=255)
    last_command = models.TextField(null=True, blank=True)
    last_output = models.TextField(null=True, blank=True)
    command_id = models.UUIDField(null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True) 

    def __str__(self):
        return self.client_id