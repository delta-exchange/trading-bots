from functools import wraps
from time import sleep
import socket
import requests
import json
import custom_exceptions


def check_requests_error(client, status_code, error_msg=None):
    if status_code == 401:
        raise custom_exceptions.AuthenticationError(client)
    elif status_code == 400:
        if 'InsufficientMargin' == error_msg:
            raise custom_exceptions.InsufficientMarginError(client)
        elif 'InvalidOrder' == error_msg:
            raise custom_exceptions.InvalidOrder(client)
        elif 'MarketDisrupted' == error_msg:
            raise custom_exceptions.MarketDisrupted(client)
        else:
            raise custom_exceptions.BadRequestError(client)
    elif status_code == 422:
        raise custom_exceptions.BadRequestError(client)
    elif status_code == 429:
        raise custom_exceptions.TooManyRequestsError(client)
    elif status_code == 501:
        raise custom_exceptions.ServiceUnavailabeError(client)
    elif status_code == 502:
        raise custom_exceptions.ServiceUnavailabeError(client)
    elif status_code == 503:
        raise custom_exceptions.ServiceUnavailabeError(client)
    elif status_code == 504:
        raise custom_exceptions.ServiceUnavailabeError(client)
    elif status_code == 500:
        raise custom_exceptions.ServiceUnavailabeError(client)
    else:
        raise custom_exceptions.UnknownError(client)


def handle_requests_exceptions(client):
    def inner_function(make_request):
        def wrapper(*args, **kwargs):
            logger = args[0].logger
            try:
                response = make_request(*args, **kwargs)
                return response
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                try:
                    logger.info('%s Exception: %s ' %
                                (client, e.response.text))
                    error_msg = e.response.json()['error']
                    check_requests_error(
                        client, status_code, error_msg)
                except Exception:
                    logger.info(str(e))
                    check_requests_error(client, status_code)
        return wraps(make_request)(wrapper)
    return inner_function
