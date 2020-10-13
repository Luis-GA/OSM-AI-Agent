from base64 import b64decode
import ast
import logging
import os
from pymongo import MongoClient
from prom_lib.prometheus_client import PrometheusClient

logger = logging.getLogger("AI-Agent")
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_handler.setFormatter(stream_formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)


def get_prometheus_data():
    client = PrometheusClient('http://192.168.33.20:9091')
    query = 'osm_cpu_utilization'
    instance = '192.168.33.133:9100'
    ts_data = client.range_query(query, instance, step=120, days=2) # returns PrometheusData object
    timeseries = ts_data['result'][0]['values']
    #with open('timeseries.json', 'w') as outfile:
    #    json.dump(timeseries, outfile)

def get_ns_info():
    client = MongoClient('mongo', 27017)
    osm = client['osm']
    values = {}

    vnf = os.environ.get('vnf-id')
    vnf_data = list(osm['vnfrs'].find({'_id': vnf}))[0]
    values['member-vnf-index-ref'] = vnf_data['member-vnf-index-ref']
    values['nsi_id'] = vnf_data['nsr-id-ref']
    ips = {}
    for vdu in vnf_data.get('vdur'):
        result = ips.get(vdu.get('vdu-id-ref'))
        if result:
            if isinstance(result, list):
                result.append(vdu.get('ip-address'))
                ips[vdu.get('vdu-id-ref')] = result
            else:
                ip_list = [result]
                ip_list.append(vdu.get('ip-address'))
                ips[vdu.get('vdu-id-ref')] = ip_list
        else:
            ips[vdu.get('vdu-id-ref')] = vdu.get('ip-address')
    values['ip-address'] = ips

    ns_data = list(osm['nsrs'].find({'_id': values['nsi_id']}))[0]

    values['ns_name'] = ns_data.get('name')
    values['vnfs'] = ns_data.get('constituent-vnfr-ref', [])

    return values

if __name__ == '__main__':
    logger.info('Dummy AI Agent')
    logger.info('Environment variables:\n{}'.format(os.environ))
    config = os.environ.get('config')
    # server = os.environ.get('server')
    #requests.post('http://8ca7ab4651c3.ngrok.io', data={'vnf': os.environ.get('HOSTNAME')})

    if config:
        config = b64decode(config)
        config = ast.literal_eval(config.decode())
        logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')

    logger.info("Now the database:")


    logger.info(get_ns_info())

