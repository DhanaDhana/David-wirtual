
from requests_oauthlib import OAuth2Session
from django.conf import settings
import os
from django.contrib.auth.models import User
from .models import OutlookCredentials

graph_url = settings.GRAPH_URL

# This is necessary for testing with non-HTTPS localhost
# Remove this if deploying to production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# This is necessary because Azure does not guarantee
# to return scopes in the same case and order as requested
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
os.environ['OAUTHLIB_IGNORE_SCOPE_CHANGE'] = '1'

authorize_url = '{0}{1}'.format(settings.AUTHORITY, settings.AUTHORIZE_ENDPOINT)
token_url = '{0}{1}'.format(settings.AUTHORITY, settings.TOKEN_ENDPOINT)

# Method to generate a sign-in url
def get_sign_in_url(user):
    # Initialize the OAuth client
    
    user_cred = OutlookCredentials.objects.filter(user=user).first()
    if user_cred:
        aad_auth = OAuth2Session(user_cred.client_id, scope=settings.SCOPES, redirect_uri=settings.REDIRECT)
        sign_in_url, state = aad_auth.authorization_url(authorize_url, prompt='login')
        return sign_in_url, state
    else:
        return False, "Outlook Credentials missing for the user"

# Method to exchange auth code for access token
def get_token_from_code(callback_url, expected_state, user):
    user_cred = OutlookCredentials.objects.filter(user=user).first()

    aad_auth = OAuth2Session(user_cred.client_id, state=expected_state, scope=settings.SCOPES, redirect_uri=settings.REDIRECT)
    token = aad_auth.fetch_token(token_url, client_secret = user_cred.client_secret, authorization_response=callback_url)
    return token


def get_token(request):
    token = request.session['oauth_token']
    if token != None:
        # Check expiration
        now = time.time()
        # Subtract 5 minutes from expiration to account for clock skew
        expire_time = token['expires_at'] - 300
        if now >= expire_time:
            # Refresh the token
            aad_auth = OAuth2Session(settings.APP_ID, token=token, scope=settings.SCOPES, redirect_uri=settings.REDIRECT)

            refresh_params = {
              'client_id': settings.APP_ID,
              'client_secret': settings.APP_SECRET,
            }
            new_token = aad_auth.refresh_token(token_url, **refresh_params)

            # Save new token
            request.session['oauth_token'] = new_token

            # Return new access token
            return new_token

        else:
            # Token still valid, just return it
            return token


