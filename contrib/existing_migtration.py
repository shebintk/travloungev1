# views.py in your Django app

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import connections
from .serializers import *


class UserFromOtherDB(APIView):
    def post(self, request, *args, **kwargs):
        try:
            with connections['mysql_db'].cursor() as cursor:
                cursor.execute("SELECT * FROM users where is_registered=1;")
                data = cursor.fetchall()
                for row in data:
                    last_record_id = User.objects.latest('id').id
                    lastid = last_record_id+1
                    uid="TRV-CUSTOMER-"+str(lastid)
                    mobile=row[2].replace('+91', '')
                    User.objects.create_user(
                            name=row[1],
                            username=mobile,
                            mobile_number=mobile,
                            password=mobile,
                            role=3,
                            uid=uid
                        )
                return Response({'message':'user created successfully'},status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
