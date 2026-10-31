class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, param: str | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.param = param

    def body(self) -> dict:
        kind = {
            400: "invalid_request",
            401: "invalid_request",
            404: "not_found",
            413: "invalid_request",
            415: "invalid_request",
            429: "too_many_requests",
        }.get(self.status, "server_error")
        return {
            "error": {"type": kind, "code": self.code, "message": self.message, "param": self.param}
        }
