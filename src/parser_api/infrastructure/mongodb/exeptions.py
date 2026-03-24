from parser_api.infrastructure.exeptions import InfrastructureException


class MongoDBError(InfrastructureException):
    def __init__(self, message, code=500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ResultError(MongoDBError):
    def __init__(self, message, code=500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class ReaderError(ResultError):
    def __init__(self, message, code=500):
        self.message = message
        self.code = code
        super().__init__(self.message)


class WriterError(ResultError):
    def __init__(self, message, code=500):
        self.message = message
        self.code = code
        super().__init__(self.message)
