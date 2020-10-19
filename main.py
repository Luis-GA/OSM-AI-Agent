from base64 import b64decode
import json
import logging
import os

import requests
from pymongo import MongoClient
from prom_lib.prometheus_client import PrometheusClient

import datetime
from importlib import import_module

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

    timestamp = datetime.datetime.utcnow().timestamp()

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


def scale_ns(nsi_id, scale="SCALE_OUT", scalingGroup=None, vnfIndex=None):
    token = update_token()
    headers = {'Authorization': token, 'accept': 'application/json'}
    url = 'https://nbi:9999/osm/nslcm/v1/ns_instances/{}/scale'.format(nsi_id)
    scale_data = {
        "scaleType": "SCALE_VNF",
        "timeout_ns_scale": 1,
        "scaleVnfData": {
            "scaleVnfType": scale,
            "scaleByStepData": {
                "scaling-group-descriptor": "vyos-VM_autoscale",
                "scaling-policy": "string",
                "member-vnf-index": "VyOS Router"
            }
        }
    }
    response = requests.post(url, data=str(scale_data), verify=False, headers=headers)
    return response.text


def update_token():
    client = MongoClient('mongo', 27017)['osm']['tokens']
    token = os.environ.get('NBI-Token', uuid.uuid4())
    date = datetime.datetime.utcnow().timestamp()
    token_data = {'_id': token, 'issued_at': date, 'expires': date + 60,
                  'id': token, 'project_id': '20620bbd-25d9-4d37-a836-89cc2ffced62',
                  'project_name': 'admin', 'username': 'admin', 'user_id': 'acef17bd-f9a1-42d6-8bed-396d66210c09',
                  'admin': True,
                  'roles': [{'name': 'system_admin', 'id': '04f86f3a-c569-4a76-9338-c06fddc52e7a'}]}
    client.insert_one(token_data)
    token = "Bearer " + token
    return token
    #headers = {'Authorization': token, 'accept': 'application/json'}
    #requests.post('https://nbi:9999/osm/admin/v1/tokens', verify=False, headers=headers)


def evaluate_v1(config, values):
    if config['AIServer']['type'] == 'tensorflow':
        ai_url = os.path.join(config['AIServer']['url'], config['AIServer']['version'])
    else:
        ai_url = config['AIServer']['url']

    logger.info("AI URL : {}".format(ai_url))
    for prediction in config['predictions']:
        if prediction['active']:
            logger.info('Prediction to perform: {}'.format(prediction))
            url = prediction['monitoring']['url']
            if url == 'vnf':
                url = values['vdu-data']['ip-address']
            port = prediction['monitoring']['port']
            url = url + ':' + port
            data = requests.get(url).json()
            logger.info('Metrics requested')

            forecast_data = requests.post(ai_url, data=data).json()
            logger.info('prediction requested')

            threshold = prediction['threshold']
            with open('aux_functions.py', 'w') as out_file:
                out_file.write(threshold['logic'])
            evaluation_function = getattr(import_module('aux_functions'), threshold['function_name'])
            logger.info("importing evaluation function")

            if evaluation_function(forecast_data):
                logger.info("SCALING")
                scale_ns(values['nsi_id'])


if __name__ == '__main__':

    logger.info('AI Agent V3.1')
    #logger.info('Environment variables:\n{}'.format(os.environ))
    config = os.environ.get('config')

    if config:
        config = b64decode(config)
        config = json.loads(config)
        #logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')

    values = get_ns_info()
    ns_id = values['nsi_id']

    if len(values['vdu-data']) == 1:
        evaluate_v1(config, values)
