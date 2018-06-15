from tornado.web import asynchronous
from tornado.gen import coroutine

from . import ApiHandler


class ParseHandler(ApiHandler):
    @asynchronous
    @coroutine
    def get(self):
        self.set_header('Content-Type', 'text/plain')
        self.finish('OK')

    @asynchronous
    @coroutine
    def post(self):
        text = self.get_argument('text', default=None)
        language = self.get_argument('language', default=None)
        self.finish({'text': text, 'language': language})
