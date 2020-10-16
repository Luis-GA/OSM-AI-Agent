from base64 import b64decode
import ast
import logging
import os

import requests
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

    timestamp = datetime.datetime.utcnow().timestamp()
    values['token'] = osm['tokens'].find_one({'expires': {'$gt': timestamp}, 'admin': True}).get('id')

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


def scale_ns(nsi_id, token, scale="SCALE_OUT", scalingGroup=None, vnfIndex=None):
    # TODO: refactorizar
    token = "Bearer " + token
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


def update_token(token):
    token = "Bearer " + token
    headers = {'Authorization': token, 'accept': 'application/json'}
    requests.post('https://nbi:9999/osm/admin/v1/tokens', verify=False, headers=headers)



if __name__ == '__main__':

    logger.info('Dummy AI Agent V3.1')
    logger.info('Environment variables:\n{}'.format(os.environ))
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
    token = values['token']
    update_token(values['token'])

    if len(values['vdu-data']) == 2:
        scale_ns(ns_id, token, scale="SCALE_IN")
