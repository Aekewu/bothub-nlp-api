#!/usr/bin/env python
""" This module start server """
import traceback
from multiprocessing import Queue, Event

import tornado.ioloop
import tornado.escape
import json
import cloudpickle
import requests
import psutil
import uuid
import logging

from threading import Timer, Lock

from tornado import web
from tornado.web import Application, asynchronous, url
from tornado.gen import coroutine
from datetime import datetime, timedelta
from app.rasabot import RasaBotProcess, RasaBotTrainProcess
from app.models.models import Bot, Profile
from app.models.base_models import DATABASE
from app.settings import *
from app.utils import INVALID_TOKEN, DB_FAIL, DUPLICATE_SLUG, token_required, ERROR_PATTERN, MISSING_DATA, INVALID_BOT, \
    validate_uuid

logging.basicConfig(filename="bothub-nlp.log")
logger = logging.getLogger('bothub NLP - Bot Manager')
logger.setLevel(logging.DEBUG)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class BotManager(object):
    """
    Bot mananger responsible to manager all bots in this instance
    """
    _pool = {}

    def __init__(self, gc=True):
        self.redis = REDIS_CONNECTION
        self._set_instance_redis()
        self._set_server_alive()
        self.gc_test = False
        if not gc:  # pragma: no cover
            self.gc_test = True
        self.start_garbage_collector()

    def _get_bot_data(self, bot_uuid):
        bot_data = {}
        if bot_uuid in self._pool:
            logger.info('Reusing an instance...')
            bot_data = self._pool[bot_uuid]
        else:
            redis_bot = self._get_bot_redis(bot_uuid)
            if redis_bot is not None:  # pragma: no cover
                logger.info('Reusing from redis...')
                redis_bot = cloudpickle.loads(redis_bot)
                bot_data = self._start_bot_process(bot_uuid, redis_bot)
                self._pool[bot_uuid] = bot_data
                self._set_bot_on_instance_redis(bot_uuid)
            else:
                logger.info('Creating a new instance...')

                with DATABASE.execution_context():
                    try:
                        instance = Bot.get(Bot.uuid == bot_uuid)

                        bot = cloudpickle.loads(instance.bot)
                        self._set_bot_redis(bot_uuid, cloudpickle.dumps(bot))
                        bot_data = self._start_bot_process(bot_uuid, bot)
                        self._pool[bot_uuid] = bot_data
                        self._set_bot_on_instance_redis(bot_uuid)
                    except:
                        raise web.HTTPError(reason=INVALID_BOT, status_code=401)
        return bot_data

    def _get_new_answer_event(self, bot_uuid):
        return self._get_bot_data(bot_uuid)['new_answer_event']

    def _get_new_question_event(self, bot_uuid):
        return self._get_bot_data(bot_uuid)['new_question_event']

    def _get_questions_queue(self, bot_uuid):
        return self._get_bot_data(bot_uuid)['questions_queue']

    def _get_answers_queue(self, bot_uuid):
        return self._get_bot_data(bot_uuid)['answers_queue']

    def ask(self, question, bot_uuid, auth_token):
        questions_queue = self._get_questions_queue(bot_uuid)
        answers_queue = self._get_answers_queue(bot_uuid)

        if not self._pool[bot_uuid]['auth_token'] == auth_token and self._pool[bot_uuid]['private']:
            raise web.HTTPError(reason=INVALID_TOKEN, status_code=401)

        questions_queue.put(question)
        new_question_event = self._get_new_question_event(bot_uuid)
        new_question_event.set()
        new_answer_event = self._get_new_answer_event(bot_uuid)

        self._pool[bot_uuid]['last_time_update'] = datetime.now()

        new_answer_event.wait()
        new_answer_event.clear()
        return answers_queue.get()

    def start_bot_process(self, bot_uuid):  # pragma: no cover
        self._get_questions_queue(bot_uuid)

    def start_garbage_collector(self):  # pragma: no cover
        Timer(GARBAGE_COLLECTOR_TIMER, self.garbage_collector).start()

    def garbage_collector(self):  # pragma: no cover
        self._set_server_alive()
        with Lock():
            new_pool = {}
            for bot_uuid, bot_instance in self._pool.items():
                if not (datetime.now() - bot_instance['last_time_update']) >= timedelta(minutes=BOT_REMOVER_TIME):
                    self._set_bot_on_instance_redis(bot_uuid)
                    new_pool[bot_uuid] = bot_instance
                else:
                    self._remove_bot_instance_redis(bot_uuid)
                    bot_instance['bot_instance'].terminate()
            self._pool = new_pool
        logger.info("Garbage collected...")
        self._set_usage_memory()
        if not self.gc_test:
            self.start_garbage_collector()

    def _get_bot_redis(self, bot_uuid):
        return redis.Redis(connection_pool=self.redis).get(bot_uuid)

    def _set_bot_redis(self, bot_uuid, bot):
        return redis.Redis(connection_pool=self.redis).set(bot_uuid, bot)

    def _set_bot_on_instance_redis(self, bot_uuid):
        if redis.Redis(connection_pool=self.redis).set("BOT-%s" % bot_uuid, self.instance_ip, ex=SERVER_ALIVE_TIMER):
            server_bots = str(
                redis.Redis(connection_pool=self.redis).get("SERVER-%s" % self.instance_ip), "utf-8").split()
            server_bots.append("BOT-%s" % bot_uuid)
            server_bots = " ".join(map(str, server_bots))

            if redis.Redis(connection_pool=self.redis).set("SERVER-%s" % self.instance_ip, server_bots):
                logger.info("Bot set in redis")
                return

        logger.warning("Error on saving bot on Redis instance, trying again...")  # pragma: no cover
        return self._set_bot_on_instance_redis(bot_uuid)  # pragma: no cover

    def _set_instance_redis(self):
        if not DEBUG:
            self.instance_ip = requests.get(AWS_URL_INSTANCES_INFO).text
        else:
            self.instance_ip = LOCAL_IP

        update_servers = redis.Redis(connection_pool=self.redis).get("SERVERS_INSTANCES_AVAILABLES")

        if update_servers is not None:
            update_servers = str(update_servers, "utf-8").split()
        else:  # pragma: no cover
            update_servers = []

        update_servers.append(self.instance_ip)
        update_servers = " ".join(map(str, update_servers))

        if redis.Redis(connection_pool=self.redis).set("SERVER-%s" % self.instance_ip, "") and \
                redis.Redis(connection_pool=self.redis).set("SERVERS_INSTANCES_AVAILABLES", update_servers):
            logger.info("Set instance in redis")
            return

        logger.critical("Error save instance in redis, trying again")  # pragma: no cover
        return self._set_instance_redis()  # pragma: no cover

    def _remove_bot_instance_redis(self, bot_uuid):
        if redis.Redis(connection_pool=self.redis).delete("BOT-%s" % bot_uuid):
            server_bot_list = str(
                redis.Redis(connection_pool=self.redis).get("SERVER-%s" % self.instance_ip), "utf-8").split()
            server_bot_list.remove("BOT-%s" % bot_uuid)
            server_bot_list = " ".join(map(str, server_bot_list))

            if redis.Redis(connection_pool=self.redis).set("SERVER-%s" % self.instance_ip, server_bot_list):
                logger.info("Removing bot from Redis")
                return

        logger.warning("Error remove bot in instance redis, trying again...")
        return self._remove_bot_instance_redis(bot_uuid)

    @staticmethod
    def _start_bot_process(bot_uuid, model_bot):
        answers_queue = Queue()
        questions_queue = Queue()
        new_question_event = Event()
        new_answer_event = Event()
        bot = RasaBotProcess(questions_queue, answers_queue,
                             new_question_event, new_answer_event, model_bot)
        bot.daemon = True
        bot.start()
        with DATABASE.execution_context():
            bot = Bot.get(Bot.uuid == bot_uuid)

        return {
            'bot_instance': bot,
            'answers_queue': answers_queue,
            'questions_queue': questions_queue,
            'new_question_event': new_question_event,
            'new_answer_event': new_answer_event,
            'last_time_update': datetime.now(),
            'auth_token': bot.owner.uuid.hex,
            'private': bot.private
        }

    def _set_server_alive(self):
        if redis.Redis(connection_pool=self.redis).set("SERVER-ALIVE-%s" % self.instance_ip, True,
                                                       ex=SERVER_ALIVE_TIMER):
            logger.info("Ping redis, i'm alive")
            return
        logger.warning("Error on ping redis, trying again...")  # pragma: no cover
        return self._set_server_alive()  # pragma: no cover

    def _set_usage_memory(self):  # pragma: no cover
        update_servers = redis.Redis(connection_pool=self.redis).get("SERVERS_INSTANCES_AVAILABLES")
        if update_servers is not None:
            update_servers = str(update_servers, "utf-8").split()
        else:
            update_servers = []

        usage_memory = psutil.virtual_memory().percent
        if usage_memory <= MAX_USAGE_MEMORY:
            if self.instance_ip not in update_servers:
                update_servers.append(self.instance_ip)
        else:
            if self.instance_ip in update_servers:
                update_servers.remove(self.instance_ip)

        update_servers = " ".join(map(str, update_servers))

        if redis.Redis(connection_pool=self.redis).set("SERVERS_INSTANCES_AVAILABLES", update_servers):
            logger.info("Servers set up available")
            return

        logger.warning("Error on set servers availables, trying again...")  # pragma: no cover
        return self._set_usage_memory()  # pragma: no cover


class BothubBaseHandler(web.RequestHandler):

    def write_error(self, status_code, **kwargs):
        self.set_header('Content-Type', 'application/json')
        if self.settings.get("serve_traceback") and "exc_info" in kwargs:
            lines = []
            for line in traceback.format_exception(*kwargs["exc_info"]):
                lines.append(line)
            self.finish(json.dumps({
                'error': {
                    'code': status_code,
                    'message': self._reason,
                    'traceback': lines,
                }
            }))
        else:
            self.finish(json.dumps({
                'error': {
                    'code': status_code,
                    'message': self._reason,
                }
            }))


class MessageRequestHandler(BothubBaseHandler):
    """
    Tornado request handler to predict data
    """
    bot_manager = None

    def initialize(self, bot_manager):
        self.bot_manager = bot_manager

    @asynchronous
    @coroutine
    @token_required
    def get(self):
        auth_token = self.request.headers.get('Authorization')[7:]
        bot = self.get_argument('bot', None)
        message = self.get_argument('msg', None)

        if message and bot and validate_uuid(bot):
            answer = self.bot_manager.ask(message, bot, auth_token)
            if answer != (ERROR_PATTERN % INVALID_TOKEN):
                data = {
                    'bot': dict(uuid=bot),
                    'answer': answer
                }
                self.write(data)
                self.finish()
            else:
                raise web.HTTPError(reason=INVALID_TOKEN, status_code=401)
        else:
            raise web.HTTPError(reason=MISSING_DATA, status_code=401)


class BotTrainerRequestHandler(BothubBaseHandler):
    """
    Tornado request handler to train bot
    """

    @asynchronous
    @token_required
    def post(self):
        if self.request.body:
            json_body = tornado.escape.json_decode(self.request.body)
            auth_token = self.request.headers.get('Authorization')[7:]
            language = json_body.get("language", None)
            bot_slug = json_body.get("slug", None)
            data = json.dumps(json_body.get("data", None))
            private = json_body.get("private", False)

            bot = RasaBotTrainProcess(language, data, self.callback, auth_token, bot_slug, private)
            bot.daemon = True
            bot.start()
        else:
            raise web.HTTPError(reason=MISSING_DATA, status_code=401)

    def callback(self, data):
        if isinstance(data, web.HTTPError):
            self.set_status(data.status_code, data.reason)
            self.write_error(data.status_code)
            return

        self.write(data)
        self.finish()


class ProfileRequestHandler(BothubBaseHandler):
    """
    Tornado request handler to predict data
    """

    @staticmethod
    def _register_profile():
        with DATABASE.execution_context():
            profile = Profile.create()
            profile.save()

        response = dict(uuid=profile.uuid.hex)
        return dict(user=response)

    @asynchronous
    @coroutine
    @token_required
    def get(self):
        with DATABASE.execution_context():
            owner_profile = Profile.select().where(
                Profile.uuid == uuid.UUID(self.request.headers.get('Authorization')[7:]))

            owner_profile = owner_profile.get()
            bots = Bot.select(Bot.uuid, Bot.slug).where(Bot.owner == owner_profile).dicts()

        bots_response = list(map(self._prepare_bot_response, bots))

        self.write(dict(bots=bots_response))
        self.finish()

    @staticmethod
    def _prepare_bot_response(bot):
        bot['uuid'] = str(bot['uuid'])
        return bot

    @asynchronous
    @coroutine
    def post(self):
        self.write(self._register_profile())
        self.finish()


class BotInformationsRequestHandler(BothubBaseHandler):
    """
    Tornado request handler to get information of specific bot (intents, entities, etc)
    """

    @asynchronous
    @coroutine
    @token_required
    def get(self):
        bot_uuid = self.get_argument('uuid', None)
        if bot_uuid and validate_uuid(bot_uuid):
            with DATABASE.execution_context():
                instance = Bot.select(Bot.uuid, Bot.slug, Bot.intents, Bot.private, Bot.owner)\
                    .where(Bot.uuid == bot_uuid)

                if len(instance):
                    instance = instance.get()
                    information = {
                        'slug': instance.slug,
                        'intents': instance.intents,
                        'private': instance.private
                    }
                    if not instance.private:
                        self.write(information)
                    else:
                        owner_profile = Profile.select().where(
                            Profile.uuid == uuid.UUID(self.request.headers.get('Authorization')[7:])).get()
                        if instance.owner == owner_profile:
                            self.write(information)
                        else:
                            raise web.HTTPError(reason=INVALID_TOKEN, status_code=401)
                    self.finish()
                else:
                    raise web.HTTPError(reason=INVALID_BOT, status_code=401)
        else:
            raise web.HTTPError(reason=INVALID_BOT, status_code=401)


def make_app():  # pragma: no cover
    return Application([
        url(r'/v1/auth', ProfileRequestHandler),
        url(r'/v1/message', MessageRequestHandler, {'bot_manager': BotManager()}),
        url(r'/v1/bots', BotInformationsRequestHandler),
        url(r'/v1/bots-redirect', MessageRequestHandler),
        url(r'/v1/train', BotTrainerRequestHandler)
    ])


def start_server(port):
    global app
    app = make_app()
    app.listen(port)
    tornado.ioloop.IOLoop.current().start()
