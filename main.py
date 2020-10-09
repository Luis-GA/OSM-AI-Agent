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
    client = MongoClient('mongo', 27017)
    osm = client['osm']

    logger.info(osm.collection_names())

