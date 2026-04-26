class PayoutError(Exception):
    """Base for all domain errors."""


class InsufficientBalance(PayoutError):
    pass


class IdempotencyConflict(PayoutError):
    """Same key, different request body."""


class IdempotencyInFlight(PayoutError):
    """Same key, original request still being processed."""


class InvalidStateTransition(PayoutError):
    pass


class BankAccountNotFound(PayoutError):
    pass
