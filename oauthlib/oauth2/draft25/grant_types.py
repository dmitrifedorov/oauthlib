"""
oauthlib.oauth2.draft_25.errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from oauthlib.common import generate_token, add_params_to_uri
from oauthlib.uri_validate import is_absolute_uri
import json
import errors


class AuthorizationBase(object):

    def validate_request(self, request):

        if not request.client_id:
            raise errors.InvalidRequestError(state=request.state,
                    description=u'Missing client_id parameter.')

        if not request.response_type:
            raise errors.InvalidRequestError(state=request.state,
                    description=u'Missing response_type parameter.')

        if not self.validate_client(request.client_id):
            raise errors.UnauthorizedClientError(state=request.state)

        if not request.response_type in self.response_type_handlers:
            raise errors.UnsupportedResponseTypeError(state=request.state)

        if request.scopes:
            if not self.validate_scopes(request.client_id, request.scopes):
                raise errors.InvalidScopeError(state=request.state)
        else:
            request.scopes = self.get_default_scopes(request.client_id)

        if request.redirect_uri:
            if not is_absolute_uri(request.redirect_uri):
                raise errors.InvalidRequestError(state=request.state,
                        description=u'Non absolute redirect URI. See RFC3986')

            if not self.validate_redirect_uri(request.client_id, request.redirect_uri):
                raise errors.AccessDeniedError(state=request.state)
        else:
            request.redirect_uri = self.get_default_redirect_uri(request.client_id)
            if not request.redirect_uri:
                raise errors.AccessDeniedError(state=request.state)

        return True

    def validate_client(self, client, *args, **kwargs):
        raise NotImplementedError('Subclasses must implement this method.')

    def validate_scopes(self, client, scopes):
        raise NotImplementedError('Subclasses must implement this method.')

    def validate_redirect_uri(self, client, redirect_uri):
        raise NotImplementedError('Subclasses must implement this method.')

    def get_default_redirect_uri(self, client):
        raise NotImplementedError('Subclasses must implement this method.')

    def get_default_scopes(self, client):
        raise NotImplementedError('Subclasses must implement this method.')


class AuthorizationCodeGrant(AuthorizationBase):

    @property
    def expires_in(self):
        return 3600

    def create_token(self):
        return {
            u'access_token': generate_token(),
            u'refresh_token': generate_token(),
            u'expires_in': self.expires_in,
            u'scope': ' '.join(self.scopes),
        }

    def create_code(self, request):
        """Generates an authorization grant represented as a dictionary."""
        grant = {u'code': generate_token()}
        if request.state:
            grant[u'state'] = request.state
        return grant

    def create_authorization_grant(self, request):
        """Generates an authorization grant represented as a dictionary."""
        grant = {u'code': generate_token()}
        if request.state:
            grant[u'state'] = request.state
        return grant

    def save_authorization_grant(self, client_id, grant, state=None):
        """Saves authorization codes for later use by the token endpoint.

        code:   The authorization code generated by the authorization server.
                The authorization code MUST expire shortly after it is issued
                to mitigate the risk of leaks. A maximum authorization code
                lifetime of 10 minutes is RECOMMENDED.

        state:  A CSRF protection value received from the client.
        """
        raise NotImplementedError('Subclasses must implement this method.')

    def create_authorization_response(self, request):
        try:
            self.validate_request(request)

        except errors.OAuth2Error as e:
            return add_params_to_uri(request.redirect_uri, e.twotuples)

        self.grant = self.create_authorization_grant(request)
        self.save_authorization_grant(request.client_id, self.grant,
                                 state=request.state)
        return add_params_to_uri(request.redirect_uri, self.grant.items())

    def create_token_response(self, request, token_handler):
        """Validate the authorization code.

        The client MUST NOT use the authorization code more than once. If an
        authorization code is used more than once, the authorization server
        MUST deny the request and SHOULD revoke (when possible) all tokens
        previously issued based on that authorization code. The authorization
        code is bound to the client identifier and redirection URI.
        """
        request.code = request.params.get(u'code')
        request.redirect_uri = request.params.get(u'redirect_uri')

        try:
            self.validate_request(request)

        except errors.OAuth2Error as e:
            return e.json

        self.scopes = self.get_scopes(request.client, request.code)
        self.token = self.create_token()
        self.token = token_handler(self.token)
        # TODO: save token
        return json.dumps(self.token)

    def validate_token_request(self, request):

        if not request.grant_type == u'authorization_code':
            raise errors.UnsupportedGrantTypeError()

        if not request.code:
            raise errors.InvalidRequestError(
                    description=u'Missing code parameter.')

        if not self.validate_client(request.client, request.grant_type):
            raise errors.UnauthorizedClientError()

        if not self.validate_code(request.client, request.code):
            raise errors.InvalidGrantError()

    def validate_code(self, client, code):
        raise NotImplementedError('Subclasses must implement this method.')


class ImplicitGrant(AuthorizationBase):

    @property
    def expires_in(self):
        return 3600

    def create_token(self, request):
        return {
            u'access_token': generate_token(),
            u'expires_in': self.expires_in,
            u'scope': ' '.join(request.scopes),
            u'state': request.state
        }

    def save_grant(self, client_id, grant, state=None):
        raise NotImplementedError('Subclasses must implement this method.')

    def create_authorization_response(self, request, token_handler):
        try:
            self.validate_request(request)

        except errors.OAuth2Error as e:
            return add_params_to_uri(
                    request.redirect_uri, e.twotuples, fragment=True)

        self.token = self.create_token(request)
        self.token = token_handler(self, self.token)
        self.save_grant(request.client_id, self.token, state=request.state)
        return add_params_to_uri(
                request.redirect_uri, self.token.items(), fragment=True)
