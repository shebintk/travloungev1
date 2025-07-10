# from billing.mongo_views import log_url_hit

# class URLHitMiddleware:
#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         # Call log_url_hit to log the URL hit
#         log_url_hit(request)
#         response = self.get_response(request)
#         return response