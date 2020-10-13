from base64 import b64decode
import ast
import logging
import os
from pymongo import MongoClient
from prom_lib.prometheus_client import PrometheusClient
from mon_client import MonClient

logger = logging.getLogger("AI-Agent")
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

    logger.info('Dummy AI Agent')
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
    if len(values['vdu-data']) == 1:
        client = MonClient()
        alarm_uuid = await client.create_alarm(metric_name='osm_average_memory_utilization', ns_id=ns_id,
                            vdu_name=values['vdu-data'][0]['name'], vnf_member_index=values['member-vnf-index-ref'],
                            threshold=80, statistic='AVERAGE', operation='LT')
        logger.info("ALARM id is {}".format(alarm_uuid))
