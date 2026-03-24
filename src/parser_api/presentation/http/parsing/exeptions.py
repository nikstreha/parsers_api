class AppError(Exception):
    def __init__(self, message: str, code: str = "internal_error"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass
