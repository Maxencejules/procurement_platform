class WorkflowError(ValueError):
    """Expected workflow failure, safe to expose through the API."""

    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(message)
        self.code = code
