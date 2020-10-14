# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import yaml
from aiokafka import AIOKafkaConsumer
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

import logging
from http import HTTPStatus

from threading import Lock


class MsgException(Exception):
    """
    Base Exception class for all msgXXXX exceptions
    """

    def __init__(self, message, http_code=HTTPStatus.SERVICE_UNAVAILABLE):
        """
        General exception
        :param message:  descriptive text
        :param http_code: <http.HTTPStatus> type. It contains ".value" (http error code) and ".name" (http error name
        """
        self.http_code = http_code
        Exception.__init__(self, "messaging exception " + message)


class MsgBase(object):
    """
    Base class for all msgXXXX classes
    """

    def __init__(self, logger_name='msg', lock=False):
        """
        Constructor of FsBase
        :param logger_name: logging name
        :param lock: Used to protect simultaneous access to the same instance class by several threads:
            False, None: Do not protect, this object will only be accessed by one thread
            True: This object needs to be protected by several threads accessing.
            Lock object. Use thi Lock for the threads access protection
        """
        self.logger = logging.getLogger(logger_name)
        if not lock:
            self.lock = FakeLock()
        elif lock is True:
            self.lock = Lock()
        elif isinstance(lock, Lock):
            self.lock = lock
        else:
            raise ValueError("lock parameter must be a Lock class or boolean")

    def connect(self, config):
        pass

    def disconnect(self):
        pass

    def write(self, topic, key, msg):
        raise MsgException("Method 'write' not implemented", http_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    def read(self, topic):
        raise MsgException("Method 'read' not implemented", http_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    async def aiowrite(self, topic, key, msg, loop=None):
        raise MsgException("Method 'aiowrite' not implemented", http_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    async def aioread(self, topic, loop=None, callback=None, aiocallback=None, group_id=None, **kwargs):
        raise MsgException("Method 'aioread' not implemented", http_code=HTTPStatus.INTERNAL_SERVER_ERROR)

class FakeLock:
    """Implements a fake lock that can be called with the "with" statement or acquire, release methods"""
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def acquire(self):
        pass

    def release(self):
        pass


class MsgKafka(MsgBase):
    def __init__(self, logger_name='msg', lock=False):
        super().__init__(logger_name, lock)
        self.host = None
        self.port = None
        self.consumer = None
        self.producer = None
        self.loop = None
        self.broker = None
        self.group_id = None

    def connect(self, config):
        try:
            if "logger_name" in config:
                self.logger = logging.getLogger(config["logger_name"])
            self.host = config["host"]
            self.port = config["port"]
            self.loop = config.get("loop") or asyncio.get_event_loop()
            self.broker = str(self.host) + ":" + str(self.port)
            self.group_id = config.get("group_id")

        except Exception as e:  # TODO refine
            raise MsgException(str(e))

    def disconnect(self):
        try:
            pass
            # self.loop.close()
        except Exception as e:  # TODO refine
            raise MsgException(str(e))

    def write(self, topic, key, msg):
        """
        Write a message at kafka bus
        :param topic: message topic, must be string
        :param key: message key, must be string
        :param msg: message content, can be string or dictionary
        :return: None or raises MsgException on failing
        """
        retry = 2   # Try two times
        while retry:
            try:
                self.loop.run_until_complete(self.aiowrite(topic=topic, key=key, msg=msg))
                break
            except Exception as e:
                retry -= 1
                if retry == 0:
                    raise MsgException("Error writing {} topic: {}".format(topic, str(e)))

    def read(self, topic):
        """
        Read from one or several topics.
        :param topic: can be str: single topic; or str list: several topics
        :return: topic, key, message; or None
        """
        try:
            return self.loop.run_until_complete(self.aioread(topic, self.loop))
        except MsgException:
            raise
        except Exception as e:
            raise MsgException("Error reading {} topic: {}".format(topic, str(e)))

    async def aiowrite(self, topic, key, msg, loop=None):
        """
        Asyncio write
        :param topic: str kafka topic
        :param key: str kafka key
        :param msg: str or dictionary  kafka message
        :param loop: asyncio loop. To be DEPRECATED! in near future!!!  loop must be provided inside config at connect
        :return: None
        """

        if not loop:
            loop = self.loop
        try:
            self.producer = AIOKafkaProducer(loop=loop, key_serializer=str.encode, value_serializer=str.encode,
                                             bootstrap_servers=self.broker)
            await self.producer.start()
            await self.producer.send(topic=topic, key=key, value=yaml.safe_dump(msg, default_flow_style=True))
        except Exception as e:
            raise MsgException("Error publishing topic '{}', key '{}': {}".format(topic, key, e))
        finally:
            await self.producer.stop()

    async def aioread(self, topic, loop=None, callback=None, aiocallback=None, group_id=None, from_beginning=None,
                      **kwargs):
        """
        Asyncio read from one or several topics.
        :param topic: can be str: single topic; or str list: several topics
        :param loop: asyncio loop. To be DEPRECATED! in near future!!!  loop must be provided inside config at connect
        :param callback: synchronous callback function that will handle the message in kafka bus
        :param aiocallback: async callback function that will handle the message in kafka bus
        :param group_id: kafka group_id to use. Can be False (set group_id to None), None (use general group_id provided
                         at connect inside config), or a group_id string
        :param from_beginning: if True, messages will be obtained from beginning instead of only new ones.
                               If group_id is supplied, only the not processed messages by other worker are obtained.
                               If group_id is None, all messages stored at kafka are obtained.
        :param kwargs: optional keyword arguments for callback function
        :return: If no callback defined, it returns (topic, key, message)
        """

        if not loop:
            loop = self.loop
        if group_id is False:
            group_id = None
        elif group_id is None:
            group_id = self.group_id
        try:
            if isinstance(topic, (list, tuple)):
                topic_list = topic
            else:
                topic_list = (topic,)
            self.consumer = AIOKafkaConsumer(loop=loop, bootstrap_servers=self.broker, group_id=group_id,
                                             auto_offset_reset="earliest" if from_beginning else "latest")
            await self.consumer.start()
            self.consumer.subscribe(topic_list)

            async for message in self.consumer:
                if callback:
                    callback(message.topic, yaml.safe_load(message.key), yaml.safe_load(message.value), **kwargs)
                elif aiocallback:
                    await aiocallback(message.topic, yaml.safe_load(message.key), yaml.safe_load(message.value),
                                      **kwargs)
                else:
                    return message.topic, yaml.safe_load(message.key), yaml.safe_load(message.value)
        except KafkaError as e:
            raise MsgException(str(e))
        finally:
            await self.consumer.stop()
