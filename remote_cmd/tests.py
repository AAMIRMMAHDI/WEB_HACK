from django.test import TestCase
from .models import Client
from django.utils import timezone
import uuid

class ClientModelTest(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            client_id='test_client',
            token='test_token',
            last_seen=timezone.now(),
            last_command='dir',
            command_id=uuid.uuid4(),
            last_output='dir output'
        )

    def test_client_str(self):
        self.assertEqual(str(self.client), 'test_client')