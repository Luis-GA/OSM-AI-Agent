from base64 import b64decode
import ast
import logging
import os
import requests

from prom_lib.prometheus_client import PrometheusClient

logger = logging.getLogger("AI-Agent")
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_handler.setFormatter(stream_formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)


def get_prometheus_data():
    client = PrometheusClient('http://localhost:9090')
    query = '(100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100))'
    instance = '192.168.33.133:9100'
    ts_data = client.range_query(query, instance, step=60, days=2)  # returns PrometheusData object


if __name__ == '__main__':
    logger.info('Dummy AI Agent')
    logger.info('Environment variables:\n{}'.format(os.environ))
    config = os.environ.get('config')
    requests.get('http://7582202cdd18.ngrok.io/')
    if config:
        config = b64decode(config)
        config = ast.literal_eval(config.decode())
        logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')
