from base64 import b64decode
import ast
import logging
import os

logger = logging.getLogger("AI-Agent")
stream_handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s: %(message)s')
stream_handler.setFormatter(stream_formatter)
logger.setLevel(logging.DEBUG)
logger.addHandler(stream_handler)

if __name__ == '__main__':
    logger.info('Dummy AI Agent')
    logger.info('Environment variables:\n{}'.format(os.environ))
    config = os.environ.get('config')
    if config:
        config = b64decode(config)
        config = ast.literal_eval(config.decode())
        logger.info('Config:\n{}'.format(config))
    else:
        logger.info('No config available')



