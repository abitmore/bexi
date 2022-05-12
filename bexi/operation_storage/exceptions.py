class OperationStorageException(Exception):
    """
    General purpose exception for the interface.
    Any and all exceptions thrown by implementations must be
    of this class
    """
    pass


class OperationStorageLostException(OperationStorageException):
    pass


class OperationStorageBadRequestException(OperationStorageException):
    pass


class AddressAlreadyTrackedException(OperationStorageException):
    pass


class AddressNotTrackedException(OperationStorageException):
    pass


class InputInvalidException(OperationStorageException):
    pass


class StatusInvalidException(OperationStorageException):
    pass


class NoBlockNumException(OperationStorageException):
    pass


class InvalidOperationException(OperationStorageException):
    pass


class InvalidOperationIdException(OperationStorageException):
    pass


class OperationNotFoundException(OperationStorageException):
    pass


class DuplicateOperationException(OperationNotFoundException):
    pass


class BalanceConcurrentException(OperationNotFoundException):
    pass
