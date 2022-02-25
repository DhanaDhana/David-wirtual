from django.shortcuts import render
from .models import User, OutlookCredentials
from .graph_helper import get_sign_in_url, get_token_from_code
# Create your views here.


from django.http import HttpResponseRedirect
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

def sign_in(request):
    # Get the sign-in URL
    sign_in_url, state = get_sign_in_url()
    # Save the expected state so we can validate in the callback
    request.session['auth_state'] = state
    # Redirect to the Azure sign-in page
    return HttpResponseRedirect(sign_in_url)
    

def callback(request):
    # Get the state saved in session
    expected_state = request.session.pop('auth_state', '')
    # # Make the token request
    token = get_token_from_code(request.get_full_path(), expected_state)
 
    user = User.objects.get(id=1)
    cred = OutlookCredentials.objects.get(user=user)
    token = str(token).replace("\'", "\"")
    cred.token_path.save('oauth_token.txt', ContentFile(token))
    return render(request, 'outlook_redirect.html')

