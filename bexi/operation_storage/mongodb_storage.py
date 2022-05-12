import collections
import pymongo
from pymongo import MongoClient

from ..addresses import split_unique_address
from .interface import (
    retry_auto_reconnect,
    BasicOperationStorage)
from .exceptions import (
    AddressNotTrackedException,
    AddressAlreadyTrackedException,
    InputInvalidException,
    OperationNotFoundException,
    DuplicateOperationException,
    InvalidOperationException,
    OperationStorageException)
from bitshares.amount import Amount


class MongoDBOperationsStorage(BasicOperationStorage):
    """
    Implementation of :class:`.interface.IOperationStorage` with MongoDB using the
    default implementation :class:`.interface.BasicOperationStorage`

    On creating an instance the mongodb client is setup and all
    necessary databases and collections are created.
    """

    def get_retry_exceptions(self):
        return (pymongo.errors.AutoReconnect,
                pymongo.errors.ServerSelectionTimeoutError,)

    @retry_auto_reconnect
    def __init__(self, mongodb_config, mongodb_client=None, purge=False):
        super(MongoDBOperationsStorage, self).__init__()

        if not mongodb_config:
            raise Exception("No mongo db configuration provided!")
        self._mongodb_config = mongodb_config

        # ensure defaults
        self._mongodb_config["operation_collection"] = self._mongodb_config.get("operation_collection", "operations")
        self._mongodb_config["status_collection"] = self._mongodb_config.get("status_collection", "status")
        self._mongodb_config["address_collection"] = self._mongodb_config.get("address_collection", "address")

        if not mongodb_client:
            mongodb_client = MongoClient(host=mongodb_config["seeds"],
                                         socketTimeoutMS=1000,
                                         connectTimeoutMS=1000,
                                         serverSelectionTimeoutMS=1000)

        self._db = mongodb_client[mongodb_config["db"]]

        if purge:
            mongodb_client[self._mongodb_config["db"]][self._mongodb_config["status_collection"]].drop()
            mongodb_client[self._mongodb_config["db"]][self._mongodb_config["operation_collection"]].drop()
            mongodb_client[self._mongodb_config["db"]][self._mongodb_config["address_collection"]].drop()

        # if collections doesnt exist, create it
        if mongodb_config["operation_collection"] not in\
                self._db.collection_names(include_system_collections=False):
            self._create_operations_storage()
        self._operations_storage = self._db[
            self._mongodb_config["operation_collection"]
        ]
        if mongodb_config["status_collection"] not in\
                self._db.collection_names(include_system_collections=False):
            self._create_status_storage()
        self._status_storage = self._db[
            self._mongodb_config["status_collection"]
        ]
        if mongodb_config["address_collection"] not in\
                self._db.collection_names(include_system_collections=False):
            self._create_address_storage()
        self._address_storage = self._db[
            self._mongodb_config["address_collection"]
        ]

    def _debug_print(self, operation):
        from pprint import pprint
        pprint(operation)

    def _create_address_storage(self):
        self._db.create_collection(
            self._mongodb_config["address_collection"],
            validator={
                "$jsonSchema": {
                    "type": "object",
                    "required": ["address",
                                 "usage"
                                 ],
                    "properties": {
                        "address": {"type": "string"},
                        "usage": {"type": "string",
                                  "enum": ["balance", "history_from", "history_to"]},
                    }
                }
            })
        self._db[self._mongodb_config["address_collection"]].create_index(
            [('address', pymongo.ASCENDING),
             ],
            unique=True)

    def _create_status_storage(self):
        self._db.create_collection(
            self._mongodb_config["status_collection"]
        )

    def _create_operations_storage(self):
        self._db.create_collection(
            self._mongodb_config["operation_collection"])
        self._db[self._mongodb_config["operation_collection"]].create_index(
            [('chain_identifier', pymongo.ASCENDING),
             ],
            unique=True)
        self._db[self._mongodb_config["operation_collection"]].create_index(
            [('incident_id', pymongo.ASCENDING),
             ('customer_id', pymongo.ASCENDING),
             ('status', pymongo.ASCENDING),
             ('block_num', pymongo.ASCENDING),
             ],
            unique=False)

    def _get_unique_filter(self, operation):
        """
        Given an operation a dictionary is returned that only contains the keys that
        are necessary for unique identification in the storage

        :param operation: operations struct as defined in :func:`interface.IOperationStorage.insert_operation`.
        :type operation: dict
        """
        return {"chain_identifier": operation["chain_identifier"]}

    @retry_auto_reconnect
    def track_address(self, address, usage="balance"):
        split = split_unique_address(address)
        if not split.get("customer_id") or not split.get("account_id"):
            raise OperationStorageException()
        try:
            self._address_storage.insert_one(
                {"address": address,
                 "usage": usage}
            )
        except pymongo.errors.DuplicateKeyError:
            raise AddressAlreadyTrackedException

    @retry_auto_reconnect
    def untrack_address(self, address, usage="balance"):
        result = self._address_storage.delete_one(
            {"address": address,
             "usage": usage}
        )
        if result.deleted_count == 0:
            raise AddressNotTrackedException()

    @retry_auto_reconnect
    def flag_operation_completed(self, operation):
        # do basics
        operation = super(MongoDBOperationsStorage, self).flag_operation_completed(operation)

        result = self._operations_storage.update_one(
            self._get_unique_filter(operation),
            {"$set": {"status": "completed",
                      "chain_identifier": operation["chain_identifier"]}})
        if result.modified_count == 0:
            raise OperationNotFoundException()

    @retry_auto_reconnect
    def flag_operation_failed(self, operation, message=None):
        # do basics
        operation = super(MongoDBOperationsStorage, self).flag_operation_failed(operation)

        result = self._operations_storage.update_one(
            self._get_unique_filter(operation),
            {"$set": {"status": "failed",
                      "message": message}})
        if result.modified_count == 0:
            raise OperationNotFoundException()

    @retry_auto_reconnect
    def insert_operation(self, operation):
        # do basics
        operation = super(MongoDBOperationsStorage, self).insert_operation(operation)

        try:
            self._operations_storage.insert_one(
                operation.copy()
            )
        except pymongo.errors.DuplicateKeyError:
            raise DuplicateOperationException()

    @retry_auto_reconnect
    def insert_or_update_operation(self, operation):
        # do basics
        operation = super(MongoDBOperationsStorage, self).insert_operation(operation)

        try:
            self._operations_storage.insert_one(
                operation.copy()
            )
        except pymongo.errors.DuplicateKeyError:
            # could be an update to completed ...
            if operation.get("block_num"):
                try:
                    operation.pop("status")
                    self.flag_operation_completed(operation)
                except OperationNotFoundException:
                    raise DuplicateOperationException()
            else:
                raise DuplicateOperationException()

    @retry_auto_reconnect
    def delete_operation(self, operation_or_incident_id):
        # do basics
        operation_or_incident_id = super(MongoDBOperationsStorage, self).delete_operation(operation_or_incident_id)

        if type(operation_or_incident_id) == str:
            incident_id = operation_or_incident_id
            result = self._operations_storage.delete_one(
                {"incident_id": incident_id}
            )
        else:
            result = self._operations_storage.delete_one(
                self._get_unique_filter(operation_or_incident_id))
        if result.deleted_count == 0:
            raise OperationNotFoundException()

    @retry_auto_reconnect
    def get_operation(self, incident_id):
        operation = self._operations_storage.find_one(
            {"incident_id": incident_id}
        )
        if not operation:
            raise OperationNotFoundException()
        _id = operation.pop("_id")
        return operation

    @retry_auto_reconnect
    def get_balances(self, take, continuation=None, addresses=None):
        # deprecated, redo logic according to azure storage for performance
        address_balances = collections.defaultdict(lambda: collections.defaultdict())

        if continuation is None:
            continuation = 0

        if not addresses:
            addresses = [x["address"] for x in
                         list(self._address_storage.find({"usage": "balance"}).sort([("_id", pymongo.ASCENDING)]))]
            lenAddresses = len(addresses)
            try:
                end = (min(continuation + take, lenAddresses))
            except TypeError:
                raise InputInvalidException()

            addresses = addresses[continuation:end]
            if end >= lenAddresses:
                end = None
            address_balances["continuation"] = end

        if type(addresses) == str:
            addresses = [addresses]

        for address in addresses:
            addrs = split_unique_address(address)
            max_block_number = 0
            for operation in self.get_operations_completed(
                    filter_by={
                        "customer_id": addrs["customer_id"]
                    }):
                this_block_num = operation["block_num"]

                asset_id = operation["amount_asset_id"]
                balance = Amount({
                    "asset_id": asset_id,
                    "amount": address_balances[address].get(asset_id, "0")})
                amount_value = Amount({
                    "asset_id": asset_id,
                    "amount": operation["amount_value"]})

                if addrs["account_id"] == operation["from"]:
                    # negative
                    address_balances[address][asset_id] =\
                        str(int(balance - amount_value))

                    # fee as well
                    asset_id = operation["fee_asset_id"]
                    balance = Amount({
                        "asset_id": asset_id,
                        "amount": address_balances[address].get(asset_id, "0")})
                    fee_value = Amount({
                        "asset_id": asset_id,
                        "amount": operation["fee_value"]})

                    address_balances[address][asset_id] =\
                        str(int(balance - fee_value))
                elif addrs["account_id"] == operation["to"]:
                    # positive
                    address_balances[address][asset_id] =\
                        str(int(balance + amount_value))
                else:
                    raise InvalidOperationException()
                max_block_number = max(max_block_number, this_block_num)
            if max_block_number > 0:
                address_balances[address]["block_num"] = max_block_number

        # do not return default dicts
        for key, value in address_balances.items():
            if type(value) == collections.defaultdict:
                address_balances[key] = dict(value)
        return dict(address_balances)

    def _parse_filter(self, filter_by):
        if filter_by:
            if filter_by.get("customer_id"):
                return {"customer_id": filter_by.pop("customer_id")}
            if filter_by.get("address"):
                addrs = split_unique_address(filter_by.pop("address"))
                return {"customer_id": addrs["customer_id"]}
            if filter_by.get("from"):
                addrs = split_unique_address(filter_by.pop("from"))
                return {"customer_id": addrs["customer_id"]}
            if filter_by.get("to"):
                addrs = split_unique_address(filter_by.pop("to"))
                return {"customer_id": addrs["customer_id"]}
            if filter_by:
                raise Exception("Filter not supported")
        return {}

    @retry_auto_reconnect
    def get_operations_in_progress(self, filter_by=None):
        filter_dict = {"status": "in_progress"}
        filter_dict.update(self._parse_filter(filter_by))
        return list(self._operations_storage.find(filter_dict))

    @retry_auto_reconnect
    def get_operations_completed(self, filter_by=None):
        filter_dict = {"status": "completed"}
        filter_dict.update(self._parse_filter(filter_by))
        return list(self._operations_storage.find(filter_dict))

    @retry_auto_reconnect
    def get_operations_failed(self, filter_by=None):
        filter_dict = {"status": "failed"}
        filter_dict.update(self._parse_filter(filter_by))
        return list(self._operations_storage.find(filter_dict))

    @retry_auto_reconnect
    def get_last_head_block_num(self):
        document = self._status_storage.find_one(
            {"status": "last_head_block_num"})
        if document:
            return document["last_head_block_num"]
        else:
            return 0

    @retry_auto_reconnect
    def set_last_head_block_num(self, head_block_num):
        current_last = self.get_last_head_block_num()
        if current_last >= head_block_num:
            raise Exception("Marching backwards not supported")
        self._status_storage.update_one(
            {"status": "last_head_block_num"},
            {'$set': {'last_head_block_num': head_block_num}},
            upsert=True)
