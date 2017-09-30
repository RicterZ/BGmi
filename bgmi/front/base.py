import json

import tornado.web

from bgmi import __version__
from bgmi.config import DANMAKU_API_URL
from bgmi.script import ScriptRunner

COVER_URL = '/bangumi/cover'
WEEK = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def jsonify(obj, status=200):
    return json.dumps({
        'version': __version__,
        'status': status,
        'danmaku_api': DANMAKU_API_URL,
        'cover_url': COVER_URL,
        'data': obj
    }, ensure_ascii=False)


class BaseHandler(tornado.web.RequestHandler):
    patch_list = None

    def data_received(self, chunk):
        pass

    def _add_header(self):
        self.add_header('Access-Control-Allow-Origin', 'http://localhost:8080')
        self.add_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.add_header("Access-Control-Allow-Headers",
                        "Content-Type,bgmi-token,bgmi-token, Access-Control-Allow-Headers, Authorization, X-Requested-With")

    def options(self, *args, **kwargs):
        self._add_header()
        self.finish('')

    def __init__(self, *args, **kwargs):
        if self.patch_list is None:
            runner = ScriptRunner()
            self.patch_list = runner.get_models_dict()

        super(BaseHandler, self).__init__(*args, **kwargs)
