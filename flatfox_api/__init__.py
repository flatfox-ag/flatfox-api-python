import sys
import json
import six.moves.urllib as urllib
import requests
import datetime

# Override this directly to set the token
access_token = None

# Override this for other environments
flatfox_server = 'https://flatfox.ch'


class ApiError(Exception):

    def __init__(self, message, json_response=None, status_code=None):
        super(ApiError, self).__init__(message)

        self.message = message
        self.json_response = json_response
        self.status_code = status_code

    def __str__(self):
        return "{0}: {1} {2}".format(
            type(self).__name__,
            self.message,
            "({0})".format(self.status_code) if self.status_code else "")


class InvalidRequestError(ApiError):
    pass


class PermissionError(ApiError):
    pass


class ApiRequestor(object):
    def __init__(self, access_token=None):
        self._token = access_token
        self._api_base = flatfox_server + '/api/v1/'

    def request(self, method, url, data=None):

        # Construct full url
        full_url = self._api_base + url
        if not full_url[-1] == '/':
            full_url += '/'

        # Construct authentication
        if self._token:
            sk = self._token
        else:
            sk = access_token
        auth = (sk, '')

        # Serialize and prepare data and files.
        if data:
            serialized_data, files = serialize_object(data)
        else:
            serialized_data, files = None, None

        sys.stdout.write("Flatfox Api: {0} {1}\n".format(
            method.upper(), full_url))

        if not files:
            res = self._raw_json_request(method=method, full_url=full_url,
                                         auth=auth, data=serialized_data)
        else:
            res = self._raw_multipart_request(method=method, full_url=full_url,
                                              auth=auth, data=serialized_data,
                                              files=files)

        # Handle response
        return self.interpret_response(response=res)

    def _raw_json_request(self, method, full_url, auth, data):
        request_func = getattr(requests, method.lower())
        return request_func(url=full_url, auth=auth, data=json.dumps(data),
                            headers={'Content-Type': 'application/json',
                                     'Accept': 'application/json'})

    def _raw_multipart_request(self, method, full_url, auth, data, files):
        request_func = getattr(requests, method.lower())
        return request_func(url=full_url, auth=auth, data=data, files=files)

    def interpret_response(self, response):
        try:
            json_resp = response.json()
        except Exception:
            raise ApiError(
                "Invalid response: %{0} (HTTP response code was {1})".format(
                    response.content, response.status_code))

        if not (200 <= response.status_code < 300):
            self.handle_api_error(response.status_code, json_resp)

        return json_resp

    def handle_api_error(self, status_code, json_resp):
        if status_code == 400:
            raise InvalidRequestError(str(json_resp),
                                      json_resp,
                                      status_code)
        if status_code == 404:
            raise InvalidRequestError(json_resp.get('detail'),
                                      json_resp,
                                      status_code)
        elif status_code == 403:
            raise PermissionError(json_resp.get('detail'),
                                  json_resp,
                                  status_code)
        else:
            raise ApiError(str(json_resp), json_resp, status_code)


class FlatfoxObject(dict):
    def __init__(self, id=None, key=None, **kwargs):
        super(FlatfoxObject, self).__init__(**kwargs)

        object.__setattr__(self, 'access_token', key if key else access_token)

        if id:
            self['id'] = id

    def __setattr__(self, key, value):
        """ Override for dot notation """
        # Special handling of special functions and non-value items
        if key[0] == '_' or key in self.__dict__:
            return super(FlatfoxObject, self).__setattr__(key, value)
        else:
            self[key] = value

    def __getattr__(self, key):
        """ Override for dot notation """
        # Special handling of special attrs
        if key[0] == '_':
            raise AttributeError(key)

        try:
            return self[key]
        except KeyError as err:
            raise AttributeError(*err.args)

    def refresh_from_data(self, values, access_token=None):
        self.access_token = access_token or getattr(values, 'access_token', None)

        self.clear()
        for key, value in values.items():
            super(FlatfoxObject, self).__setitem__(key, value)

    def request(self, method, url, data=None):
        requestor = ApiRequestor(access_token=self.access_token)
        response = requestor.request(method=method, url=url, data=data)
        return response

    @classmethod
    def init_from_response(cls, values, key):
        instance = cls(id=values.get('id'), key=key)
        instance.refresh_from_data(values, access_token=key)
        return instance

    @property
    def flatfox_id(self):
        return self.id


def serialize_object(obj):
    params = {}
    files = {}

    for k, v in obj.items():
        if k == 'id' or k.startswith('_'):
            continue
        elif hasattr(v, 'serialize'):
            params[k] = v.serialize()
        elif hasattr(v, 'read'):  # Check for files
            files[k] = v
        elif isinstance(v, (datetime.datetime, datetime.date,)):
            params[k] = v.isoformat()
        else:
            params[k] = v

    return params, files


def deserialize_object(klass, response, access_token):
    if isinstance(response, list):
        return [
            deserialize_object(klass, item, access_token)
            for item in response]

    elif isinstance(response, dict) and not isinstance(response, FlatfoxObject):
        return klass.init_from_response(response, key=access_token)
    else:
        return response


class ApiResource(FlatfoxObject):

    @classmethod
    def retrieve(cls, access_token=None, **params):
        instance = cls(access_token=access_token, **params)
        instance.refresh()
        return instance

    @classmethod
    def exists(cls, **params):
        try:
            instance = cls(**params)
            instance.refresh()
            return True
        except:
            return False

    def refresh(self):
        self.refresh_from_data(self.request('get', self.instance_url()))
        return self

    @classmethod
    def class_name(cls):
        if cls == ApiResource:
            raise NotImplementedError

        return str(urllib.parse.quote_plus(cls.__name__.lower()))

    @classmethod
    def class_url(cls):
        return "{0}".format(cls.class_name().lower())

    def instance_url(self):
        id = self.get('id')
        external_id = self.get('external_id')
        if not id and not external_id:
            raise InvalidRequestError(
                'Cannot get instance url of object {0}: no id is set.'.format(
                    type(self).__name__))
        base = self.class_url()
        id_part = ApiResource.format_id(id=id, external_id=external_id)
        return "{base}/{id}".format(base=base, id=id_part)

    @staticmethod
    def format_id(id=None, external_id=None):
        if id:
            res = str(id)
        else:
            res = 'ext-{0}'.format(external_id)
        return urllib.parse.quote_plus(res)


class ListableApiResource(ApiResource):
    @classmethod
    def list(cls, access_token=None, **params):
        requestor = ApiRequestor(access_token=access_token)
        url = cls.class_url()
        response = requestor.request('get', url, params)
        return deserialize_object(
            klass=cls,
            response=response,
            access_token=access_token)


class CreateableApiResource(ApiResource):
    @classmethod
    def create(cls, access_token=None, **params):
        requestor = ApiRequestor(access_token=access_token)
        url = cls.class_url()
        response = requestor.request(method='post', url=url, data=params)
        return cls(access_token=access_token, **response)


class UpdateableApiResource(ApiResource):

    def save(self):
        # params, files = serialize_object(self)
        res = self.request(method='put', url=self.instance_url(), data=self)
        self.refresh_from_data(res)
        return self


class Flat(ListableApiResource, UpdateableApiResource, CreateableApiResource):

    @classmethod
    def class_url(cls):
        return "my-flat"

    @classmethod
    def init_from_response(cls, values, key):
        images = values.pop('images', [])
        flat = super(Flat, cls).init_from_response(values, key)
        flat.images = deserialize_object(FlatImage, images, key)
        return flat


class FlatImage(CreateableApiResource):

    @classmethod
    def class_url(cls):
        return "flat-image"
