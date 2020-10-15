from base64 import b64decode
import ast
import logging
import os
from pymongo import MongoClient
from prom_lib.prometheus_client import PrometheusClient
from mon_client import MonClient
import asyncio
import json
import datetime
from message_bus_client import MessageBusClient

import uuid

logger = logging.getLogger("AI-Agent v8")
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_handler.setFormatter(stream_formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)


def get_prometheus_data(ns_id, query='', step=120, days=2):
    client = PrometheusClient('http://prometheus:9090')
    if not query:
        query = 'osm_average_memory_utilization'

    ts_data = client.range_query(query, ns_id, step=step, days=days)
    timeseries = ts_data['result'][0]['values']
    return timeseries


def get_ns_info():
    client = MongoClient('mongo', 27017)
    osm = client['osm']
    values = {}

    vnf = os.environ.get('vnf-id')
    vnf_data = list(osm['vnfrs'].find({'_id': vnf}))[0]
    values['member-vnf-index-ref'] = vnf_data['member-vnf-index-ref']
    values['nsi_id'] = vnf_data['nsr-id-ref']
    vduData = []

    for vdu in vnf_data.get('vdur'):
        vduData.append(
            {'vdu-id-ref': vdu.get('vdu-id-ref'), 'ip-address': vdu.get('ip-address'), 'name': vdu.get('name')})
    values['vdu-data'] = vduData

    ns_data = list(osm['nsrs'].find({'_id': values['nsi_id']}))[0]

    values['ns_name'] = ns_data.get('name')
    values['vnfs'] = ns_data.get('constituent-vnfr-ref', [])

    return values


if __name__ == '__main__':

    logger.info('Dummy AI Agent V3.1')
    # logger.info('Environment variables:\n{}'.format(os.environ))
    config = os.environ.get('config')

    if config:
        config = b64decode(config)
        config = ast.literal_eval(config.decode())
        logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')

    logger.info("Now the database:")
    values = get_ns_info()
    ns_id = values['nsi_id']

    logger.info(values)

    # get_prometheus_data(ns_id)
    if len(values['vdu-data']) == 99:
        logger.info("KAFKA scale action")
        date1 = datetime.datetime.now().timestamp()
        date2 = datetime.datetime.now().timestamp()
        #now = datetime.datetime.utcnow()
        #now_str = now.strftime("%d-%m-%Y %H:%M:%S")
        uid = '1b16eef4-716f-4779-96fc-78979667a77a'# str(uuid.uuid1()) '086cfe47-9930-4a29-8168-487eac45bd89'
        """
        message = {'schema_version': '1.1', 'schema_type': 'notify_alarm',
                   'notify_details': {'alarm_uuid': uid,
                                      'metric_name': 'osm_average_memory_utilization', 'threshold_value': 80.0,
                                      'operation': 'lt', 'severity': 'critical', 'status': 'insufficient-data',
                                      'start_date': str(now_str),
                                      'tags': {'ns_id': ns_id,
                                               'vdu_name': 'testing-ee-VyOS Router-vyos-VM-1',
                                               'vnf_member_index': 'VyOS Router'}}}"""
        """
        message = {'_admin': {'created': date1, 'modified': date1,
                              'projects_read': ['20620bbd-25d9-4d37-a836-89cc2ffced62'],
                              'projects_write': ['20620bbd-25d9-4d37-a836-89cc2ffced62']},
                   '_id': uid, 'detailedStatus': None, 'errorMessage': None,
                   'id': uid, 'isAutomaticInvocation': False, 'isCancelPending': False,
                   'lcmOperationType': 'scale',
                   'links': {'nsInstance': '/osm/nslcm/v1/ns_instances/{}'.format(ns_id),
                             'self': '/osm/nslcm/v1/ns_lcm_op_occs/{}'.format(uid)},
                   'nsInstanceId': ns_id,
                   'operationParams': {'lcmOperationType': 'scale', 'nsInstanceId': ns_id,
                                       'scaleType': 'SCALE_VNF', 'scaleVnfData': {
                           'scaleByStepData': {'member-vnf-index': 'VyOS Router',
                                               'scaling-group-descriptor': 'vyos-VM_autoscale',
                                               'scaling-policy': 'string'},
                           'scaleVnfType': 'SCALE_OUT'}, 'timeout_ns_scale': 1}, 'operationState': 'PROCESSING',
                   'queuePosition': None, 'stage': None, 'startTime': date2,
                   'statusEnteredTime': date2}"""



        """
        loop = asyncio.get_event_loop()
        kafka_server = '{}:{}'.format('kafka', '9092')
        producer = AIOKafkaProducer(loop=loop,
                                    bootstrap_servers=kafka_server,
                                    key_serializer=str.encode,
                                    value_serializer=str.encode)

        loop.run_until_complete(producer.start())
        try:
            loop.run_until_complete(producer.send_and_wait("alarm_response", key="notify_alarm", value=json.dumps(msg)))
        finally:
            loop.run_until_complete(producer.stop())
        logger.info("KAFKA scale action triggered")
        """

        """
        client = MonClient()
        loop = asyncio.get_event_loop()
        alarm_uuid = loop.run_until_complete(
            client.create_alarm(metric_name='osm_average_memory_utilization', ns_id=ns_id,
                                vdu_name=values['vdu-data'][0]['name'],
                                vnf_member_index=values['member-vnf-index-ref'], threshold=80,
                                statistic='AVERAGE', operation='LT'))

        logger.info("ALARM id is {}".format(alarm_uuid))"""

        message = {'_admin': {'created': date2, 'modified': date2,
                    'projects_read': ['20620bbd-25d9-4d37-a836-89cc2ffced62'],
                    'projects_write': ['20620bbd-25d9-4d37-a836-89cc2ffced62']},
         '_id': uid, 'detailedStatus': None, 'errorMessage': None,
         'id': uid, 'isAutomaticInvocation': False, 'isCancelPending': False,
         'lcmOperationType': 'scale',
         'links': {'nsInstance': '/osm/nslcm/v1/ns_instances/{}'.format(ns_id),
                   'self': '/osm/nslcm/v1/ns_lcm_op_occs/{}'.format(uid)},
         'nsInstanceId': '{}'.format(ns_id),
         'operationParams': {'lcmOperationType': 'scale', 'nsInstanceId': ns_id,
                             'scaleType': 'SCALE_VNF', 'scaleVnfData': {
                 'scaleByStepData': {'member-vnf-index': 'VyOS Router', 'scaling-group-descriptor': 'vyos-VM_autoscale',
                                     'scaling-policy': 'string'}, 'scaleVnfType': 'SCALE_OUT'}, 'timeout_ns_scale': 1},
         'operationState': 'PROCESSING', 'queuePosition': None, 'stage': None, 'startTime': date1,
         'statusEnteredTime': date1}

        logger.info("Luis {}".format(message))
        loop = asyncio.get_event_loop()
        msg_bus = MessageBusClient()
        loop.run_until_complete(msg_bus.aiowrite('ns', 'scale', message))

        logger.info("Terminado")