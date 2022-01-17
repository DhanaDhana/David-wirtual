import threading
from rest_framework.authtoken.models import Token
from re import sub


class RequestUserMiddleware:
    thread_local = threading.local()
    
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and later middleware) are called.
        
        logged_in_user = None
        header_token = request.META.get('HTTP_AUTHTOKEN', None)
        if header_token is not None:
          try:
            token = sub('token ', '', header_token.lower())
            token_obj = Token.objects.get(key = token)
            logged_in_user = token_obj.user
          except Token.DoesNotExist:
            pass
        RequestUserMiddleware.thread_local.current_user = logged_in_user
        
        response = self.get_response(request)

        # Code to be executed for each request/response after
        # the view is called.

        return response

