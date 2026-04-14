import json
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


SERVICE_MAP = settings.GATEWAY_SERVICE_MAP


@csrf_exempt
def proxy_view(request, service, path=''):
    """Proxy requests to the appropriate microservice."""
    base_url = SERVICE_MAP.get(service)
    if not base_url:
        return JsonResponse({'error': 'Service not found'}, status=404)

    url = f"{base_url}/api/{service}/{path}"
    if not url.endswith('/'):
        url += '/'

    headers = {}
    if request.headers.get('Authorization'):
        headers['Authorization'] = request.headers['Authorization']
    headers['Content-Type'] = 'application/json'

    try:
        if request.method == 'GET':
            resp = requests.get(url, params=request.GET, headers=headers, timeout=10)
        elif request.method == 'POST':
            body = json.loads(request.body) if request.body else {}
            resp = requests.post(url, json=body, headers=headers, timeout=10)
        elif request.method == 'PUT':
            body = json.loads(request.body) if request.body else {}
            resp = requests.put(url, json=body, headers=headers, timeout=10)
        elif request.method == 'DELETE':
            resp = requests.delete(url, headers=headers, timeout=10)
        else:
            return JsonResponse({'error': 'Method not allowed'}, status=405)

        try:
            data = resp.json()
        except ValueError:
            data = {'message': resp.text}

        return JsonResponse(data, status=resp.status_code, safe=False)
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': f'Service unavailable: {str(e)}'}, status=503)


def home_page(request):
    return render(request, 'index.html')


def customer_login_page(request):
    return render(request, 'customer_login.html')


def staff_login_page(request):
    return render(request, 'staff_login.html')


def get_full_api(request):
    return render(request, 'swagger.html')
