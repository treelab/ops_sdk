"""
处理API请求
"""
from abc import ABC

from shortuuid import uuid
import traceback
from .cache_context import cache_conn
from tornado.web import RequestHandler, HTTPError
from .jwt_token import AuthToken, jwt


class BaseHandler(RequestHandler, ABC):
    def __init__(self, *args, **kwargs):
        self.new_csrf_key = str(uuid())
        self.business_id, self.resource_group = None, None
        self.user_id, self.username, self.nickname, self.email, self.is_super = None, None, None, None, False
        self.is_superuser = self.is_super
        self.token_verify = False
        self.params = {}
        super(BaseHandler, self).__init__(*args, **kwargs)

    def get_params_dict(self):
        self.params = {k: self.get_argument(k) for k in self.request.arguments}
        if "filter_map" in self.params:
            try:
                import json
                filter_map = self.params.get('filter_map')
                filter_map = json.loads(filter_map)
            except:
                filter_map = {}
        else:
            filter_map = {}
        self.params['filter_map'] = filter_map

        if self.request_resource_map and isinstance(self.request_resource_map, dict):
            self.params['filter_map'] = {**filter_map, **self.request_resource_map}
        if "auth_key" in self.params:
            self.params.pop('auth_key')

    def opex_csrf(self):
        # 验证客户端CSRF，如请求为GET，则不验证，否则验证。最后将写入新的key
        cache = cache_conn()
        if self.request.method in ("GET", "HEAD", "OPTIONS") or self.request.headers.get('Sdk-Method'):
            pass
        else:
            csrf_key = self.get_cookie('csrf_key')
            if not csrf_key:
                raise HTTPError(402, 'csrf error need csrf key')
            result = cache.get(csrf_key)
            cache.delete(csrf_key)
            if isinstance(result, bytes):
             result = result.decode()
            if result != '1':
                raise HTTPError(402, 'csrf error')
            cache.set(self.new_csrf_key, '1', ex=24*60*60)
            self.set_cookie('csrf_key', self.new_csrf_key)

    def opex_login(self):
        # 登陆验证
        auth_key = self.get_cookie('auth_key') if self.get_cookie("auth_key") else self.request.headers.get('auth-key')
        if not auth_key:
            auth_key = self.get_argument('auth_key', default=None, strip=True)

        if not auth_key:
            raise HTTPError(401, 'auth failed')

        if self.token_verify:
            auth_token = AuthToken()
            user_info = auth_token.decode_auth_token(auth_key)
        else:
            user_info = jwt.decode(auth_key, options={"verify_signature": False}).get('data')

        if not user_info:
            raise HTTPError(401, 'auth failed')

        self.user_id = user_info.get('user_id', None)
        self.username = user_info.get('username', None)
        self.nickname = user_info.get('nickname', None)
        self.email = user_info.get('email', None)
        self.is_super = user_info.get('is_superuser', False)

        if not self.user_id: raise HTTPError(401, 'auth failed')

        self.user_id = str(self.user_id)
        self.set_secure_cookie("user_id", self.user_id)
        self.set_secure_cookie("nickname", self.nickname)
        self.set_secure_cookie("username", self.username)
        self.set_secure_cookie("email", str(self.email))
        self.is_superuser = self.is_super

    def initialize(self, *args, **kwargs):
        pass

    def prepare(self):
        # 获取url参数为字典
        self.get_params_dict()
        # 验证客户端CSRF
        self.opex_csrf()

        # 登陆验证
        self.opex_login()

    def get_current_user(self):
        return self.username

    def get_current_id(self):
        return self.user_id

    def get_current_nickname(self):
        return self.nickname

    def get_current_email(self):
        return self.email

    def is_superuser(self):
        return self.is_superuser

    @property
    def request_resource_group(self):
        if not self.resource_group:
            self.resource_group = self.get_secure_cookie("resource_group") if self.get_secure_cookie(
                "resource_group") else self.request.headers.get('resource-group')

            if not self.resource_group: return None
            if isinstance(self.resource_group, bytes):  self.resource_group = bytes.decode(self.resource_group)
            return self.resource_group

        return self.resource_group

    @property
    def request_resource_map(self):
        if self.request_resource_group in [None, 'all', '所有项目']:
            return dict()
        else:
            return dict(resource_group=self.request_resource_group)

    @property
    def request_business_id(self):
        if not self.business_id:
            self.business_id = self.get_secure_cookie("business_id") if self.get_secure_cookie("business_id") else \
                self.request.headers.get('biz-id')
            if not self.business_id: return None
            if isinstance(self.business_id, bytes):  self.business_id = bytes.decode(self.business_id)
            return self.business_id

        return self.business_id

    @property
    def request_username(self):
        return self.username

    @property
    def request_user_id(self):
        return self.user_id

    @property
    def request_nickname(self):
        return self.nickname

    @property
    def request_email(self):
        return self.email

    @property
    def request_is_superuser(self):
        return self.is_superuser

    def write_error(self, status_code, **kwargs):
        error_trace_list = traceback.format_exception(*kwargs.get("exc_info"))
        if status_code == 404:
            self.set_status(status_code)
            return self.finish('找不到相关路径-404')

        elif status_code == 400:
            self.set_status(status_code)
            return self.finish('bad request...')

        elif status_code == 402:
            self.set_status(status_code)
            return self.finish('csrf error...')

        elif status_code == 403:
            self.set_status(status_code)
            return self.finish('Sorry, you have no permission. Please contact the administrator')

        if status_code == 500:
            self.set_status(status_code)
            for line in error_trace_list:
                self.write(str(line))
            self.finish()

        elif status_code == 401:
            self.set_status(status_code)
            return self.finish('你没有登录')

        else:
            self.set_status(status_code)


class LivenessProbe(RequestHandler, ABC):
    def initialize(self, *args, **kwargs):
        pass

    def head(self):
        self.write(dict(code=0, msg="I'm OK"))

    def get(self):
        self.write(dict(code=0, msg="I'm OK"))
