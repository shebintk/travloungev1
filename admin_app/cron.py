import requests
from django.http import JsonResponse
from firebase_admin import db

def update_toloo_rooms(request):
    firebase_api_key = 'AIzaSyBV7b3vmVFJ7SBjQ1JMQcMPtUvxSNOs_Vk'
    firebase_database_url = 'https://travlounge-c3bb6-default-rtdb.asia-southeast1.firebasedatabase.app/'
    firebase_endpoint = f'{firebase_database_url}/.json?auth={firebase_api_key}'
    try:
        response = requests.get(firebase_endpoint)
        production_ref = response.json()
        production_data = production_ref.get("toloo", {})
        develop_ref = db.reference("toloo")
        develop_data = develop_ref.get()
        for room_key, room_value in production_data.items():
            if room_key in develop_data:
                develop_data[room_key].update(room_value)

        develop_ref.update(develop_data)

        return JsonResponse({'production': production_data, 'develop': develop_data})
    except requests.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)
