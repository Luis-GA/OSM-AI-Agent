import requests
from datetime import datetime, timedelta
import time


class PrometheusClient:
    apibase = "/api/v1/"

    def __init__(self, prometheus_url="http://localhost:9090"):
        self.apibase = "/api/v1/"
        self.prometheus_url = prometheus_url if prometheus_url[-1:] != '/' else prometheus_url[:-1]

    def range_query(self, metric, instance=None, start=None, end=None, step=60, params=None, days=1):
        """
        Returns a PrometheusData object loaded with results from a query_range call
        :param instance: instance to query
        :param days: Number of days to query
        :param metric: string of the metric query
        :param start: an epoch time for the earliest data point in the range -- default is 24 hours ago
        :param end: an epoch time for the latest data point in the range -- default is the current time
        :param step: the step size
        :param params: additional params to send to the API
        :return: PrometheusData
        """
        if params is None:
            params = {}

        params['query'] = metric
        params['instance'] = instance
        params['step'] = step

        if start is None:
            start = self._time_to_epoch((datetime.now() - timedelta(days=days)))

        if end is None:
            end = self._time_to_epoch(datetime.now())

        params['start'] = start
        params['end'] = end

        response = self._fetch('query_range', params)
        data = self._extract_data(response)
        return data

    @staticmethod
    def _time_to_epoch(t):
        """
        A simple utility to turn a datetime object into a timestamp
        :param t: datetime object
        :return: integer
        """
        return int(time.mktime(t.timetuple()))

    def _fetch(self, resource, params=None):
        if params is None:
            params = {}
        full_url = self.prometheus_url + self.apibase + resource
        res = requests.get(full_url, params)
        return res.json()

    @staticmethod
    def _extract_data(jsondata):
        if jsondata['status'] != 'success':
            data = []
        else:
            data = jsondata['data']
        return data

    @staticmethod
    def _handle_results(data):
        results = data
        return results
