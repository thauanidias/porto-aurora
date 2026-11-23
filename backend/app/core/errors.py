class DomainError(Exception):
    def __init__(self, message: str, status: int = 422, code: str = "VALIDATION_ERROR"):
        self.message = message
        self.status = status
        self.code = code
