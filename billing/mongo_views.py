# import datetime
# from django.http import HttpResponse, request

# # from rest_framework.response import Response
# from billing.models import *
# from admin_app.models import *
# from customer.models import *
# from store_admin.models import *

# from pymongo import MongoClient
# from urllib.parse import quote_plus
# import os


# def log_url_hit(request):
   
#     path = request.path
#     # url_hit = URLHit(path=path)
#     # url_hit.save()
#     username = 'travelounge_usr'
#     password = 'dTCexnT3mzOaoWgY'
#     cluster_name = 'travloungecluster'
# # Escape the username and password using quote_plus
#     escaped_username = quote_plus(username)
#     escaped_password = quote_plus(password)
#     connection_string = f"mongodb+srv://travelounge_usr:dTCexnT3mzOaoWgY@travloungecluster.jvkpuzk.mongodb.net/?retryWrites=true&w=majority"
    
#     # Create a MongoClient object and connect to the MongoDB instance
#     client = MongoClient(connection_string)

#     # Access the desired database
#     db = client['travloungev1_db']

#     # Access the desired collection within the database
#     collection = db['travloungev1_collection']

#     timestamp = datetime.datetime.now()

#     # Perform database operations
#     # Example: Insert a document into the collection
#     document = {
#         'path': path,
#         'timestamp': timestamp
#     }
#     result = collection.insert_one(document)
#     print('Inserted document ID:', result.inserted_id)
#     # result = collection.delete_many({})
#     # print('Number of documents deleted:', result.deleted_count)
    
#     # Close the MongoDB connection
#     client.close()
#     return HttpResponse('URL logged')
