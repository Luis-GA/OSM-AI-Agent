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


def get_prometheus_data(ns_id, query, step=120, days=2):
    """
    Prometheus data requester
    :param ns_id: network service instance id
    :param query: prometheus query
    :param step: time between probe and probe (in seconds)
    :param days: interval of data (current datetime - days, current datetime)
    :return: Prometheus data: List of tuples [(value of metric, timestamp), ...]
    """
    client = PrometheusClient('http://prometheus:9090')
    ts_data = client.range_query(query, ns_id, step=step, days=days)
    timeseries = ts_data['result'][0]['values']
    return timeseries


def get_ns_info():
    """
    Network service data requester using MongoDB as datasource
    :return: Network Service Data with the following structure:
                {
                'member-vnf-index-ref': <string>,
                'nsi_id': <string>,
                'vdu-data': <list>,
                'ns_name': <string>,
                'vnfs': <list>,
                'project_id': <string>,
                'scaling-group-descriptor': <string>
                }
    """
    client = MongoClient('mongo', 27017)
    osm = client['osm']
    values = {}

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
    """
    Scale in/out trigger for NS.
    :param nsi_id:  Network Service instance identification
    :param project_id: OSM Project identification
    :param scaling_group: Scaling group action (Specified  in the VNF descriptor)
    :param vnf_index: Virtual Network Function index (Specified  in the VNF descriptor)
    :param scale: Scale action 2 possibilities: 'SCALE_OUT' Or 'SCALE_IN'
    :return: Scaling action response
    """
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
    delete_token(token)
    return response.text


def update_token(project_id):
    """
    NBI Token generator to provide authorization access
    :param project_id: OSM Project identification
    :return: token to perform requests in an authorized way
    """
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


def delete_token(token):
    """
    Remove used token for scaling actions to be deleted
    :param token: token used
    :return: None
    """
    token = token.split('Bearer ')[-1]
    client = MongoClient('mongo', 27017)['osm']['tokens']
    client.delete_one({'id': token})


def url_composer(url, port=None):
    """
    URL composer
    :param url: URL to compose
    :param port: optional port to compose
    :return: composed URL
    """
    if url[0] != 'h':
        url = 'http://{}'.format(url)
    if port:
        url = url + ':' + str(port)
    return url


def get_metrics(prediction, values):
    """
    Metrics requester in evaluation phase
    :param prediction: prediction object defined in the helm chart values
    :param values: values obtained by the function get_ns_info
    :return: metrics
    """
    data = []
    url = prediction['monitoring'].get('url')
    prom_query = prediction['monitoring'].get('prometheusQuery')
    if url:
        url = prediction['monitoring']['url']
        if url == 'vnf':
            url = values['vdu-data']['ip-address']
        port = prediction['monitoring']['port']
        url = url_composer(url, port)
        data = requests.get(url).text
    elif prom_query:
        stepsTime = prediction['monitoring'].get('stepsTime') * 60
        dataWindowTime = prediction['monitoring'].get('dataWindowTime') / 1440

        data = get_prometheus_data(values['nsi_id'], prom_query, step=stepsTime, days=dataWindowTime)

    logger.info('Metrics requested')
    return data


def ai_evaluation(prediction, ai_url, data):
    """
    AI evaluation asking the AI Server and being evaluated by the threshold defined in the helm chart
    :param prediction: prediction object defined in the helm chart values
    :param ai_url: AI URL defined in the helm chart
    :param data: metrics data
    :return: True for scaling, False for not scaling
    """
    url = ai_url.format(prediction['model'])
    forecast_data = requests.post(url, data=data).json()
    logger.info('prediction requested: {}'.format(forecast_data))

    threshold = prediction['threshold']
    with open('aux_functions.py', 'w') as out_file:
        out_file.write(threshold['logic'])
    evaluation_function = getattr(import_module('aux_functions'), threshold['function_name'])
    logger.info("importing evaluation function")

    return evaluation_function(forecast_data)


def evaluate_v1(config, values):
    """
    Evaluation function V1
    :param config: configuration object defined in the helm chart values
    :param values: values obtained by the function get_ns_info
    :return: None
    """
    if config['AIServer']['type'] == 'tensorflow':
        ai_url = os.path.join(config['AIServer']['url'], config['AIServer']['version'], 'models') + '/{}:predict'
    else:
        ai_url = config['AIServer']['url']
    ai_url = url_composer(ai_url)
    logger.info("AI URL : {}".format(ai_url))

    for prediction in config['predictions']:
        if prediction['active']:
            logger.info('Prediction to perform: {}'.format(prediction))
            data = get_metrics(prediction, values)

            evaluation = ai_evaluation(prediction, ai_url, data)

            if evaluation and (len(values['vdu-data']) == 1):
                logger.info("SCALING OUT")
                scale_ns(values['nsi_id'], values['project_id'], values['scaling-group-descriptor'],
                         values['member-vnf-index-ref'])
            elif not evaluation and len(values['vdu-data']) > 1:
                logger.info("SCALING IN")
                scale_ns(values['nsi_id'], values['project_id'], values['scaling-group-descriptor'],
                         values['member-vnf-index-ref'], scale="SCALE_IN")


if __name__ == '__main__':

    logger.info('AI Agent V1.0')
    config = os.environ.get('config')

    if config:
        config = b64decode(config)
        config = json.loads(config)
        logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')

    values = get_ns_info()
    logger.info('Values:\n{}'.format(values))

    evaluate_v1(config, values)
