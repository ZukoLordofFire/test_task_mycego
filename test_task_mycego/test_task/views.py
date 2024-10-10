from typing import Any, Dict, List, Optional

from django.contrib.sessions.backends.db import SessionStore
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from oauthlib.oauth2 import WebApplicationClient
import requests
import urllib
from urllib.parse import parse_qs, quote_plus, urlparse

# Ключи приложения, полученные при регистрации на Яндекс.Разработчики
CLIENT_ID = "9cbed2c57fbe4f91ac44c58440de1fe1"
CLIENT_SECRET = "fbaf082788ba47c7a484dad2f53890cd"
REDIRECT_URI = "http://127.0.0.1:8000/callback"
SCOPE: List[str] = []

client = WebApplicationClient(CLIENT_ID)

authorization_url = client.prepare_request_uri(
    'https://oauth.yandex.ru/authorize',
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
)


def authorize(request):
    """
    Перенаправляет пользователя на страницу авторизации Яндекса.
    """
    return redirect(authorization_url)


# Токен доступа
access_token: Optional[str] = None


def index(request):
    """
    Отображает главную страницу.
    """
    return render(request, "index.html")


def callback(request):
    """
    Обрабатывает ответ от Яндекса после авторизации.
    """
    # Получение кода авторизации
    code: Optional[str] = request.GET.get('code')

    # Обмен кода авторизации на токен доступа
    token_url = 'https://oauth.yandex.ru/token'
    token_data: Dict[str, str] = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
    }
    token_response = requests.post(token_url, data=token_data)

    # Проверка ответа
    if token_response.status_code == 200:
        token: Dict[str, Any] = token_response.json()
        request.session['token'] = token
        return redirect('index')
    else:
        return render(
            request, 'index.html', {'error': 'Ошибка при получении токена доступа'}
        )


def files(request):
    """
    Отображает список файлов с Яндекс.Диска.
    """
    # Проверка авторизации
    token: Optional[Dict[str, Any]] = request.session.get('token')
    if not token:
        return redirect('authorize')

    # Получение public_key из URL-параметров
    public_key: Optional[str] = request.POST.get('public_key')
    request.session['public_key'] = public_key
    if not public_key:
        return render(
            request, 'files.html', {'error': 'Не указана публичная ссылка'}
        )

    # Запрос к API Яндекс.Диска
    headers = {'Authorization': 'OAuth ' + token['access_token']}
    url = f'https://cloud-api.yandex.net/v1/disk/public/resources?public_key={public_key}'
    response = requests.get(url, headers=headers)
    # Обработка ответа
    if response.status_code == 200:
        data: Dict[str, Any] = response.json()
        files: List[Dict[str, Any]] = data.get('_embedded', {}).get('items', [])
        context = {
            'files': files,  # Передача data в контекст
            'public_key': public_key,
            'access_token': token['access_token'],
        }

        # Добавляем ссылки для скачивания файлов
        for file in files:
            file['download_url'] = reverse(
                'download',
                args=[file['path']]
            )

        return render(request, 'files.html', context)
    else:
        return render(
            request, 'files.html', {'error': 'Ошибка при получении файлов'}
        )
 

def download(request, file_path: str) -> HttpResponse:
    """
    Скачивает файл с Яндекс.Диска по указанному пути.

    Args:
        request: Запрос от клиента.
        file_path: Путь к файлу на Яндекс.Диске.

    Returns:
        FileResponse: Ответ с файлом, если скачивание прошло успешно.
        HttpResponse: Ответ с ошибкой, если произошла ошибка.
    """
    public_key: Optional[str] = request.session.get('public_key')
    token: Optional[Dict[str, str]] = request.session.get('token')
    if not token:
        return redirect('authorize')

    # Замена пробелов на %20 в file_path
    path_encoded = quote_plus(file_path.encode('utf-8'))

    # Формирование запроса для получения download_url
    download_url_request = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={public_key}&path={path_encoded.replace('/', '%2F')}"
    print(download_url_request)

    response = requests.get(
        download_url_request,
        headers={"Authorization": f"OAuth {token['access_token']}"}
    )

    if response.status_code == 200:
        data = response.json()
        download_url = data['href']

        # Скачивание файла по download_url
        file_response = requests.get(download_url, stream=True)

        # Установка заголовков для ответа
        parsed_url = urlparse(download_url)
        query_params = parse_qs(parsed_url.query)
        filename = query_params['filename'][0]

        # Возврат файла клиенту
        return FileResponse(
            file_response.raw,
            as_attachment=True,
            filename=filename,
            content_type=file_response.headers['Content-Type'],
        )
    else:
        return HttpResponse(f"Ошибка: {response.status_code}", status=response.status_code)