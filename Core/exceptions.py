class InsufficientFundsError(Exception):
    """Raised when a wallet does not have enough balance for a debit."""
    def __init__(self, message: str = "Insufficient funds"):
        self.message = message
        super().__init__(self.message)

