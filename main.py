from base64 import b64decode
import json
import logging
import os

import requests
from pymongo import MongoClient, DESCENDING
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
    vnf_data = osm['vnfrs'].find_one({'_id': vnf})
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
    values['project_id'] = ns_data.get('_admin').get('projects_write', [None])[0]
    scaling = osm['vnfds'].find_one({'_id': vnf_data['vnfd-id']}).get('scaling-group-descriptor', [{}])[0].get('name')
    values['scaling-group-descriptor'] = scaling
    return values


def scale_ns(nsi_id, project_id, scaling_group, vnf_index, scale="SCALE_OUT"):
    token = update_token(project_id)
    headers = {'Authorization': token, 'accept': 'application/json'}
    url = 'https://nbi:9999/osm/nslcm/v1/ns_instances/{}/scale'.format(nsi_id)
    scale_data = {
        "scaleType": "SCALE_VNF",
        "timeout_ns_scale": 1,
        "scaleVnfData": {
            "scaleVnfType": scale,
            "scaleByStepData": {
                "scaling-group-descriptor": scaling_group,
                "scaling-policy": "string",
                "member-vnf-index": vnf_index
            }
        }
    }
    response = requests.post(url, data=str(scale_data), verify=False, headers=headers)
    return response.text


def update_token(project_id):
    client = MongoClient('mongo', 27017)['osm']['tokens']
    token = os.environ.get('NBI-Token', uuid.uuid4())
    date = datetime.datetime.utcnow().timestamp()
    token_data = client.find_one({'project_id': project_id}, sort=[('expires', DESCENDING)])
    token_data['_id'] = token
    token_data['id'] = token
    token_data['issued_at'] = date
    token_data['expires'] = date + 5

    try:
        client.delete_one({'id': token})
    except Exception as e:
        logger.debug(e)

    client.insert_one(token_data)
    token = "Bearer " + token
    return token
    # headers = {'Authorization': token, 'accept': 'application/json'}
    # requests.post('https://nbi:9999/osm/admin/v1/tokens', verify=False, headers=headers)


def url_composer(url, port=None):
    if url[0] != 'h':
        url = 'http://{}'.format(url)
    if port:
        url = url + ':' + str(port)
    return url


def evaluate_v1(config, values):
    if config['AIServer']['type'] == 'tensorflow':
        ai_url = os.path.join(config['AIServer']['url'], config['AIServer']['version'], 'models')
    else:
        ai_url = config['AIServer']['url']
    ai_url = url_composer(ai_url)
    logger.info("AI URL : {}".format(ai_url))

    for prediction in config['predictions']:
        if prediction['active']:
            logger.info('Prediction to perform: {}'.format(prediction))
            url = prediction['monitoring']['url']
            if url == 'vnf':
                url = values['vdu-data']['ip-address']
            port = prediction['monitoring']['port']
            url = url_composer(url, port)

            data = requests.get(url).text
            logger.info('Metrics requested')
            model_path = '/' + prediction['model'] + ':predict'
            forecast_data = requests.post(ai_url + model_path, data=data).json()
            logger.info('prediction requested: {}'.format(forecast_data))

            threshold = prediction['threshold']
            with open('aux_functions.py', 'w') as out_file:
                out_file.write(threshold['logic'])
            evaluation_function = getattr(import_module('aux_functions'), threshold['function_name'])
            logger.info("importing evaluation function")

            if evaluation_function(forecast_data) and (len(values['vdu-data']) == 1):
                logger.info("SCALING OUT")
                scale_ns(values['nsi_id'], values['project_id'], values['scaling-group-descriptor'],
                         values['member-vnf-index-ref'])
            elif (not evaluation_function(forecast_data)) and len(values['vdu-data']) > 1:
                logger.info("SCALING IN")
                scale_ns(values['nsi_id'], values['project_id'], values['scaling-group-descriptor'],
                         values['member-vnf-index-ref'], scale="SCALE_IN")


if __name__ == '__main__':

    logger.info('AI Agent V3.1')
    # logger.info('Environment variables:\n{}'.format(os.environ))
    config = os.environ.get('config')

    if config:
        config = b64decode(config)
        config = json.loads(config)
        # logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')

    values = get_ns_info()
    logger.info('values: {}'.format(values))
    ns_id = values['nsi_id']

    evaluate_v1(config, values)
