class LSPTimeoutError(Exception):
    pass


class LSPError(Exception):
    def __init__(self, code, message, data=None):
        self.code = code
        self.data = data
        super().__init__(f"LSP error {code}: {message}")
