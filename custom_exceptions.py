class Error(Exception):
    pass


class SocketConnectionError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 500


class BadGatewayError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 502


class ServiceUnavailabeError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 503


class PlaceOrderError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class InsufficientMarginError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class LowerThanBankruptcyError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class LowOrderSizeError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class ContractExpiredError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class EditOrderError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class MarketDisrupted(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class InvalidOrder(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class BadRequestError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 400


class TooManyRequestsError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 429


class InternalServerError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 503


class AuthenticationError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 401


class ForbiddenError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 403


class NonceError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 401


class UnknownError(Error):
    def __init__(self, client):
        self.client = client
        self.status_code = 1000
