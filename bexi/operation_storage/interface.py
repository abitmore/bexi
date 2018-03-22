from abc import ABC, abstractmethod
from ..operation_storage import operation_formatter
from ..utils import date_to_string
from .. import Config
import time


class OperationStorageException(Exception):
    """
    General purpose exception for the interface.
    Any and all exceptions thrown by implementations must be
    of this class
    """
    pass


class OperationStorageLostException(OperationStorageException):
    pass


class AddressAlreadyTrackedException(OperationStorageException):
    pass


class AddressNotTrackedException(OperationStorageException):
    pass


class StatusInvalidException(OperationStorageException):
    pass


class NoBlockNumException(OperationStorageException):
    pass


class InvalidOperationException(OperationStorageException):
    pass


class OperationNotFoundException(OperationStorageException):
    pass


class DuplicateOperationException(OperationNotFoundException):
    pass


class IOperationStorage(ABC):

    @abstractmethod
    def flag_operation_completed(self, operation):
        """
        Marks an operation that is in_progress as completed.

        :param operation: operations struct as defined in :func:`interface.IOperationStorage.insert_operation`.
        :type operation: dict
        :raises: StatusInvalidException: if the operation status is not in_progress
        :raises: NoBlockNumException: if no block_num was given
        :raises: InvalidOperationException: if the operation is not well defined or couldnt be found
        :raises: OperationNotFoundException: if the given operation cant be found in the storage
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def flag_operation_failed(self, operation, message=None):
        """
        Marks an operation that is in_progress as failed.

        :param operation: operations struct adhering to the json schema definitions
        :type operation: dict
        :param message: reason of failure
        :type message: str
        :raises: StatusInvalidException: if the operation status is not in_progress
        :raises: OperationNotFoundException: if the given operation cant be found in the storage
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def insert_operation(self, operation):
        """
        Inserts the operation into the storage. Operation status
        can be in_progress or completed.

        :param operation: operations struct adhering to the json schema definitions
        :type operation: dict
        :raises: InvalidOperationException: if the operation is not well defined
        :raises: DuplicateOperationException: if the operation already exists in the storage
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def insert_or_update_operation(self, operation):
        """
        Inserts the operation, or updates it into the storage. Operation status
        can be in_progress or completed

        :param operation: operations struct adhering to the json schema definitions
        :type operation: dict
        :raises: InvalidOperationException: if the operation is not well defined
        :raises: DuplicateOperationException: if the operation already exists in the storage
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def delete_operation(self, operation_or_incident_id):
        """
        Deletes an operation from the storage.

        :param operation_or_incident_id: operations struct adhering to the json schema definitions
                                         or the incident_id of the operation
        :type operation_or_incident_id: dict or string
        :raises: StatusInvalidException: if the operation status is not completed or failed
        :raises: OperationNotFoundException: if the given operation cant be found in the storage
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def get_operation(self, incident_id):
        """
        Returns the operation with the specified incident_id

        :param incident_id: incident_id of the operations
        :type incident_id: string
        :raises: OperationNotFoundException: if the given operation cant be found in the storage
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def get_operations_in_progress(self, filter_by):
        """
        Returns all operations that are in progress and follow the filter rules

        :param filter_by: rules to filter the operations
        :type filter_by: dict
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def get_operations_completed(self, filter_by):
        """
        Returns all operations that are completed and follow the filter rules

        :param filter_by: rules to filter the operations
        :type filter_by: dict
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def get_operations_failed(self, filter_by):
        """
        Returns all operations that are failed and follow the filter rules

        :param filter_by: rules to filter the operations
        :type filter_by: dict
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def get_last_head_block_num(self):
        """
        Returns the last head block num that was processed by this storage

        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def set_last_head_block_num(self, head_block_num):
        """
        Sets the last head block num that was processed by this storage

        :raises: OperationStorageLostException: any technical problems contacting the storage
        """


class IAddressOperationStorage(IOperationStorage):
    """
    Interface that defines address specific interfaces
    """

    @abstractmethod
    def track_address(self, address, usage):
        """
        Tells the storage to track the given address for the given usage.

        :param adress: as is
        :type adress: string
        :param usage: balance return the balance of the adress
                      as default in :func:`interface.IAddressOperationStorage.get_balances`.
               history_to history_from return return the transaction history of the adress, only for tracking purposes
                                       right now
        :type usage: string
        :raises: AddressAlreadyTrackedException: if the address is already tracked
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def untrack_address(self, address, usage):
        """
        Tells the storage to untrack the given address for the given usage.

        :param address: as is
        :type address: string
        :param usage: balance stop returning the balance of this address
                              as default in :func:`interface.IAddressOperationStorage.get_balances`.
               history_to history_from return return the transaction history of the adress, only for tracking purposes
                                       right now
        :raises: AddressNotTrackedException: if the address was not tracked at all
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """

    @abstractmethod
    def get_balances(self, addresses=None):
        """
        Returns the address balances of the requested address names

        :param addresses: list of requested addresses, default all tracked addresses
        :type addresses: string or list of string
        :raises: OperationStorageLostException: any technical problems contacting the storage
        """


def retry_auto_reconnect(func):
    """
    This is a decorator for functions that utilize some external storage driver.
    Any exception that reflects a connection error triggers an automatic
    retry of the given function. Those exceptions are defined in
    :func:`BasicOperationStorage.get_retry_exceptions`

    :param func: the function that will obtain retry feature
    :type func: function handle
    """

    def f_retry(self, *args, **kwargs):
        num_tries = Config.get("operation_storage", "retry_policy", "num", 3)
        wait_in_ms = Config.get("operation_storage", "retry_policy", "wait_in_ms", 0)
        exceptions = self.get_retry_exceptions()
        last_exception = None
        for i in range(num_tries):  # @UnusedVariable
            try:
                return func(self, *args, **kwargs)
            except exceptions as e:
                last_exception = e
                if wait_in_ms > 0:
                    time.sleep(wait_in_ms / 1000)
                continue
        raise OperationStorageLostException(last_exception)
    return f_retry


class BasicOperationStorage(IOperationStorage):

    @abstractmethod
    def get_retry_exceptions(self):
        """
        Returns a n-tupel with all exceptions that should trigger retry function
        """

    def _validate_operation(self, operation):
        operation_formatter.validate_operation(operation)

    def _decode_operation(self, operation):
        """
        See :func:`operation_formatter.decode_operation`
        :param operation:
        :type operation:
        """
        return operation_formatter.decode_operation(operation)

    def flag_operation_completed(self, operation):
        """
            Does simply status check and json schema validation

            :param operation: operations struct adhering to the json schema definitions
            :type operation: dict
        """

        # dont mutate input
        operation = operation.copy()

        try:
            if operation["status"] != "in_progress":
                raise StatusInvalidException()
        except KeyError:
            operation["status"] = "in_progress"
            pass

        self._validate_operation(operation)

        if not operation.get("chain_identifier"):
            raise InvalidOperationException()

        if not operation.get("block_num"):
            raise NoBlockNumException()

        return operation

    def flag_operation_failed(self, operation, message=None):
        """
            Does simply status check and json schema validation

            :param operation: operations struct adhering to the json schema definitions
            :type operation: dict
        """

        # dont mutate input
        operation = operation.copy()

        try:
            if operation["status"] != "in_progress":
                raise StatusInvalidException()
        except KeyError:
            # assume in progress
            operation["status"] = "in_progress"
            pass

        self._validate_operation(operation)

        return operation

    def insert_operation(self, operation):
        """
            Does simply status check and json schema validation

            :param operation: operations struct adhering to the json schema definitions
            :type operation: dict
        """
        # convert format if it comes directly from blockchain monitor
        if operation.get("op"):
            operation = self._decode_operation(operation)
        else:
            operation = operation.copy()

        if not operation.get("status"):
            if operation.get("block_num"):
                operation["status"] = "completed"
            else:
                operation["status"] = "in_progress"

        self._validate_operation(operation)

        if operation["status"] == "completed":
            if not operation.get("block_num"):
                raise InvalidOperationException()
        elif operation["status"] == "in_progress":
            if operation.get("block_num"):
                raise InvalidOperationException()
        else:
            raise InvalidOperationException()

        # add insertion timestamp
        operation["timestamp"] = date_to_string()

        return operation

    def delete_operation(self, operation_or_incident_id):
        """
            Does simply status check and json schema validation if an operation dict is given

            :param operation_or_incident_id: operations struct adhering to the json schema definitions, or incident_id
            :type operation_or_incident_id: dict or str
        """
        if type(operation_or_incident_id) == dict:
            # dont mutate input
            operation_or_incident_id = operation_or_incident_id.copy()

            self._validate_operation(operation_or_incident_id)
            if operation_or_incident_id["status"] == "in_progress":
                raise StatusInvalidException()

        return operation_or_incident_id
