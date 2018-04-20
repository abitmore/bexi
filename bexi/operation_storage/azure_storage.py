import time
import collections
from azure.common import AzureConflictHttpError, AzureMissingResourceHttpError,\
    AzureHttpError
from azure.cosmosdb.table.tableservice import TableService
from urllib3.exceptions import NewConnectionError

from ..addresses import split_unique_address, get_tracking_address
from .exceptions import (
    AddressNotTrackedException,
    AddressAlreadyTrackedException,
    InputInvalidException,
    OperationNotFoundException,
    DuplicateOperationException,
    InvalidOperationException,
    OperationStorageException)
from .interface import (
    retry_auto_reconnect,
    BasicOperationStorage)
from bexi import Config
import json
from json.decoder import JSONDecodeError


class AzureOperationsStorage(BasicOperationStorage):
    """
        Implementation of :class:`.interface.IOperationStorage` with Azure Table Storage using the
        default implementation :class:`.interface.BasicOperationStorage`

        On creating a connection to the storage is initialized and all needed
        tables are created. If a purge is necessary, tables are not deleted but simple the content removed.
        Table creation can take a while with Azure Table Storage.

        As Azure Table Storage only supports two indices, the operations are inserted multiple times in different
        tables to enable multi-index queries.
    """

    def get_retry_exceptions(self):
        return (NewConnectionError)

    @retry_auto_reconnect
    def __init__(self, azure_config, purge=False):
        super(AzureOperationsStorage, self).__init__()

        if not azure_config:
            raise Exception("No azure table storage configuration provided!")
        self._azure_config = azure_config

        # ensure defaults
        self._azure_config["operation_table"] = self._azure_config.get("operation_table", "operations")
        self._azure_config["address_table"] = self._azure_config.get("address_table", "address")
        self._azure_config["status_table"] = self._azure_config.get("status_table", "status")
        self._azure_config["balances_table"] = self._azure_config.get("balances_table", "balances")

        if not self._azure_config["account"]:
            raise Exception("Please include the azure account name in the config")
        if not self._azure_config["key"]:
            raise Exception("Please include the azure account key in the config")

        self._service = TableService(account_name=self._azure_config["account"], account_key=self._azure_config["key"])

        # if tables doesnt exist, create it
        self._create_operations_storage(purge)
        self._create_status_storage(purge)
        self._create_address_storage(purge)
        self._create_balances_storage(purge)

    def _debug_print(self, operation):
        from pprint import pprint
        pprint(operation)

    def _create_address_storage(self, purge):
        _varients = ["balance", "historyfrom", "historyto"]

        for variant in _varients:
            tablename = self._azure_config["address_table"] + variant
            if purge:
                try:
                    for item in self._service.query_entities(tablename):
                        self._service.delete_entity(
                            tablename,
                            item["PartitionKey"],
                            item["RowKey"])
                except AzureHttpError:
                    pass
                except AzureMissingResourceHttpError:
                    pass
            while not self._service.exists(tablename):
                self._service.create_table(tablename)
                time.sleep(0.1)

    def _create_status_storage(self, purge):
        if purge:
            try:
                tablename = self._azure_config["status_table"]
                for item in self._service.query_entities(tablename):
                    self._service.delete_entity(
                        tablename,
                        item["PartitionKey"],
                        item["RowKey"])
            except AzureMissingResourceHttpError:
                pass
        while not self._service.exists(self._azure_config["status_table"]):
            self._service.create_table(self._azure_config["status_table"])
            time.sleep(0.1)

    def _create_balances_storage(self, purge):
        if purge:
            try:
                tablename = self._azure_config["balances_table"]
                for item in self._service.query_entities(tablename):
                    self._service.delete_entity(
                        tablename,
                        item["PartitionKey"],
                        item["RowKey"])
            except AzureMissingResourceHttpError:
                pass
        while not self._service.exists(self._azure_config["balances_table"]):
            self._service.create_table(self._azure_config["balances_table"])
            time.sleep(0.1)

    def _create_operations_storage(self, purge):
        self._operation_varients = ["incident", "status"]  #  "customer"
        self._operation_tables = {}
        for variant in self._operation_varients:
            self._operation_tables[variant] = self._azure_config["operation_table"] + variant

        self._operation_prep = {
            "status": lambda op: {
                "PartitionKey": op["status"],
                "RowKey": op["chain_identifier"]
            },
            "customer": lambda op: {
                "PartitionKey": op["customer_id"],
                "RowKey": op["chain_identifier"]
            },
            "incident": lambda op: {
                "PartitionKey": self._short_digit_hash(op["incident_id"]),
                "RowKey": op["incident_id"]
            }
        }
        for variant in self._operation_varients:
            if purge:
                try:
                    tablename = self._operation_tables[variant]
                    for item in self._service.query_entities(tablename):
                        self._service.delete_entity(
                            tablename,
                            item["PartitionKey"],
                            item["RowKey"])
                except AzureMissingResourceHttpError:
                    pass
            while not self._service.exists(self._operation_tables[variant]):
                self._service.create_table(self._operation_tables[variant])
                time.sleep(0.1)

    def _get_with_ck(self, variant, operation):
        with_ck = operation.copy()
        with_ck.update(self._operation_prep[variant](with_ck))
        return with_ck

    def _short_digit_hash(self, value):
        return str(abs(hash(value)) % (10 ** Config.get("operation_storage", "short_hash_digits", 3)))

    @retry_auto_reconnect
    def track_address(self, address, usage="balance"):
        split = split_unique_address(address)
        if not split.get("customer_id") or not split.get("account_id"):
            raise OperationStorageException()
        try:
            self._service.insert_entity(
                self._azure_config["address_table"] + usage,
                {"PartitionKey": self._short_digit_hash(address),
                 "RowKey": address,
                 "address": address,
                 "usage": usage}
            )
        except AzureConflictHttpError:
            raise AddressAlreadyTrackedException

    @retry_auto_reconnect
    def untrack_address(self, address, usage="balance"):
        try:
            self._service.delete_entity(
                self._azure_config["address_table"] + usage,
                self._short_digit_hash(address),
                address)
            try:
                self._delete_balance(address)
            except AzureMissingResourceHttpError:
                pass
        except AzureMissingResourceHttpError:
            raise AddressNotTrackedException()

    @retry_auto_reconnect
    def _get_address(self, address, usage="balance"):
        try:
            self._service.get_entity(
                self._azure_config["address_table"] + usage,
                self._short_digit_hash(address),
                address)
        except AzureMissingResourceHttpError:
            raise AddressNotTrackedException()

    def _update(self, operation, status=None):
        try:
            for variant in self._operation_varients:
                operation = self._get_with_ck(variant, operation)
                new_operation = operation.copy()
                if status:
                    tmp = self.get_operation(operation["incident_id"])
                    new_operation["timestamp"] = tmp["timestamp"]
                    new_operation["status"] = status
                    new_operation = self._get_with_ck(variant, new_operation)
                if variant == "status":
                    # needs delete and insert
                    self._service.delete_entity(
                        self._operation_tables[variant],
                        operation["PartitionKey"],
                        operation["RowKey"])
                    self._service.insert_entity(
                        self._operation_tables[variant],
                        new_operation)
                else:
                    self._service.update_entity(
                        self._operation_tables[variant],
                        new_operation)
        except AzureMissingResourceHttpError:
            raise OperationNotFoundException()
        except AzureConflictHttpError:
            raise DuplicateOperationException()

    def _insert(self, operation):
        try:
            for variant in self._operation_varients:
                to_insert = operation.copy()
                to_insert.update(self._operation_prep[variant](to_insert))
                if not to_insert["PartitionKey"]:
                    raise AzureMissingResourceHttpError()
                if not to_insert["RowKey"]:
                    raise AzureMissingResourceHttpError()
                self._service.insert_entity(
                    self._operation_tables[variant],
                    to_insert
                )
        except AzureConflictHttpError:
            raise DuplicateOperationException()

    def _delete(self, operation):
        try:
            for variant in self._operation_varients:
                to_delete = operation.copy()
                to_delete.update(self._operation_prep[variant](to_delete))
                self._service.delete_entity(
                    self._operation_tables[variant],
                    to_delete["PartitionKey"],
                    to_delete["RowKey"])
        except AzureMissingResourceHttpError:
            raise OperationNotFoundException()

    @retry_auto_reconnect
    def flag_operation_completed(self, operation):
        # do basics
        operation = super(AzureOperationsStorage, self).flag_operation_completed(operation)

        self._update(operation, status="completed")

        self._ensure_balances(operation)

    @retry_auto_reconnect
    def flag_operation_failed(self, operation, message=None):
        # do basics
        operation = super(AzureOperationsStorage, self).flag_operation_failed(operation)
        operation["message"] = message
        self._update(operation, status="failed")

    @retry_auto_reconnect
    def insert_operation(self, operation):
        # do basics
        operation = super(AzureOperationsStorage, self).insert_operation(operation)

        self._insert(operation)

        if operation["status"] == "completed":
            self._ensure_balances(operation)

    @retry_auto_reconnect
    def _delete_balance(self, address):
        self._service.delete_entity(
            self._azure_config["balances_table"],
            self._short_digit_hash(address),
            address
        )

    @retry_auto_reconnect
    def _ensure_balances(self, operation):
        affected_address = get_tracking_address(operation)
        try:
            self._get_address(affected_address)
        except AddressNotTrackedException:
            # delte if exists and return
            try:
                self._delete_balance(affected_address)
            except AzureMissingResourceHttpError:
                pass
            return

        try:
            balance_dict = self._service.get_entity(
                self._azure_config["balances_table"],
                self._short_digit_hash(affected_address),
                affected_address)
            insert = False
        except AzureMissingResourceHttpError as e:
            balance_dict = {"address": affected_address}
            insert = True

        balance_dict["blocknum"] = max(balance_dict.get("blocknum", 0), operation["block_num"])
        total = 0

        addrs = split_unique_address(affected_address)
        asset_id = "balance" + operation["amount_asset_id"].split("1.3.")[1]
        if addrs["account_id"] == operation["from"]:
            # internal transfer and withdraw

            # negative
            balance = balance_dict.get(asset_id, 0)

            balance_dict[asset_id] = balance - operation["amount_value"]

            # fee as well
            asset_id = operation["fee_asset_id"]
            balance = balance_dict.get(asset_id, 0)

            balance_dict[asset_id] = balance - operation["fee_value"]
        elif addrs["account_id"] == operation["to"]:
            # deposit

            # positive
            balance = balance_dict.get(asset_id, 0)

            balance_dict[asset_id] = balance + operation["amount_value"]

            # fees were paid by someone else
        else:
            raise InvalidOperationException()

        for key, value in balance_dict.items():
            if key.startswith("balance"):
                total = total + value

        balance_dict["PartitionKey"] = self._short_digit_hash(balance_dict["address"])
        balance_dict["RowKey"] = balance_dict["address"]

        if total == 0:
            if not insert:
                try:
                    self._delete_balance(affected_address)
                except AzureMissingResourceHttpError:
                    pass
            return

        # may be updated or inserted, total > 0
        if (insert):
            try:
                self._service.insert_entity(
                    self._azure_config["balances_table"],
                    balance_dict
                )
            except AzureMissingResourceHttpError:
                raise OperationStorageException("Critical error in database consistency")
        else:
            try:
                self._service.update_entity(
                    self._azure_config["balances_table"],
                    balance_dict
                )
            except AzureConflictHttpError:
                raise OperationStorageException("Critical error in database consistency")

    @retry_auto_reconnect
    def insert_or_update_operation(self, operation):
        # do basics
        operation = super(AzureOperationsStorage, self).insert_operation(operation)

        try:
            self._insert(operation)
        except DuplicateOperationException as ex:
            # could be an update to completed ...
            if operation.get("block_num"):
                try:
                    operation.pop("status")
                    self.flag_operation_completed(operation)
                except OperationNotFoundException:
                    raise ex
            else:
                raise ex

    @retry_auto_reconnect
    def delete_operation(self, operation_or_incident_id):
        # do basics
        operation = super(AzureOperationsStorage, self).delete_operation(operation_or_incident_id)

        if type(operation_or_incident_id) == str:
            operation = self.get_operation(operation_or_incident_id)
        else:
            operation = operation_or_incident_id
        self._delete(operation)

    @retry_auto_reconnect
    def get_operation(self, incident_id):
        try:
            operation = self._service.get_entity(
                self._operation_tables["incident"],
                self._short_digit_hash(incident_id),
                incident_id)
            operation.pop("PartitionKey")
            operation.pop("RowKey")
            operation.pop("Timestamp")
            operation.pop("etag")
        except AzureMissingResourceHttpError:
            raise OperationNotFoundException()
        return operation

    @retry_auto_reconnect
    def get_balances(self, take, continuation=None, addresses=None, recalculate=False):
        if recalculate:
            raise Exception("Currently not supported due to memo change on withdraw")
            return self._get_balances_recalculate(take, continuation, addresses)
        else:
            if continuation is not None:
                try:
                    continuation_marker = json.loads(continuation)
                except TypeError:
                    raise InputInvalidException()
                except JSONDecodeError:
                    raise InputInvalidException()

                balances = self._service.query_entities(
                    self._azure_config["balances_table"],
                    num_results=take,
                    marker=continuation_marker)
            else:
                balances = self._service.query_entities(
                    self._azure_config["balances_table"],
                    num_results=take)
            return_balances = {}
            for address_balance in balances:
                return_balances[address_balance["address"]] = {
                    "block_num": address_balance["blocknum"]
                }
                for key, value in address_balance.items():
                    if key.startswith("balance"):
                        asset_id = "1.3." + key.split("balance")[1]
                        return_balances[address_balance["address"]][asset_id] = value
            return_balances["continuation"] = None
            if balances.next_marker:
                return_balances["continuation"] = json.dumps(balances.next_marker)
            return return_balances

    @retry_auto_reconnect
    def _get_balances_recalculate(self, take, continuation=None, addresses=None):
        address_balances = collections.defaultdict(lambda: collections.defaultdict())

        if not addresses:
            if continuation is not None:
                try:
                    continuation_marker = json.loads(continuation)
                except TypeError:
                    raise InputInvalidException()
                except JSONDecodeError:
                    raise InputInvalidException()

                addresses = self._service.query_entities(
                    self._azure_config["address_table"] + "balance",
                    num_results=take,
                    marker=continuation_marker)
            else:
                addresses = self._service.query_entities(
                    self._azure_config["address_table"] + "balance",
                    num_results=take)
            if addresses.next_marker:
                address_balances["continuation"] = json.dumps(addresses.next_marker)
            addresses = [x["address"] for x in addresses]

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
                if addrs["account_id"] == operation["from"]:
                    # negative
                    balance = address_balances[address].get(asset_id, 0)

                    address_balances[address][asset_id] =\
                        balance - operation["amount_value"]

                    # fee as well
                    asset_id = operation["fee_asset_id"]
                    balance = address_balances[address].get(asset_id, 0)

                    address_balances[address][asset_id] =\
                        balance - operation["fee_value"]
                elif addrs["account_id"] == operation["to"]:
                    # positive
                    balance = address_balances[address].get(asset_id, 0)

                    address_balances[address][asset_id] =\
                        balance + operation["amount_value"]
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
                return {"from": addrs["account_id"]}
            if filter_by.get("to"):
                addrs = split_unique_address(filter_by.pop("to"))
                return {"to": addrs["account_id"]}
            if filter_by:
                raise Exception("Filter not supported")
        return {}

    def _filter_dict_to_string(self, filter_dict, partition_key=None):
        filter_str = None
        for key, value in filter_dict.items():
            if partition_key == key:
                key = "PartitionKey"
            if filter_str is not None:
                delimiter = " and "
            delimiter = ""
            filter_str = delimiter + key + " eq '" + value + "'"
        return filter_str

    @retry_auto_reconnect
    def get_operations_in_progress(self, filter_by=None):
        filter_dict = {"status": "in_progress"}
        filter_dict.update(self._parse_filter(filter_by))

        filter_str = self._filter_dict_to_string(filter_dict, "status")

        return list(self._service.query_entities(
            self._operation_tables["status"],
            filter_str))

    @retry_auto_reconnect
    def get_operations_completed(self, filter_by=None):
        filter_dict = {"status": "completed"}
        filter_dict.update(self._parse_filter(filter_by))

        filter_str = self._filter_dict_to_string(filter_dict, "status")

        return list(self._service.query_entities(
            self._operation_tables["status"],
            filter_str))

    @retry_auto_reconnect
    def get_operations_failed(self, filter_by=None):
        filter_dict = {"status": "failed"}
        filter_dict.update(self._parse_filter(filter_by))

        filter_str = self._filter_dict_to_string(filter_dict, "status")

        return list(self._service.query_entities(
            self._operation_tables["status"],
            filter_str))

    @retry_auto_reconnect
    def get_last_head_block_num(self):
        try:
            document = self._service.get_entity(
                self._azure_config["status_table"],
                "head_block_num",
                "last")
            return document["last_head_block_num"]
        except AzureMissingResourceHttpError:
            return 0

    @retry_auto_reconnect
    def set_last_head_block_num(self, head_block_num):
        current_last = self.get_last_head_block_num()
        if current_last >= head_block_num:
            raise Exception("Marching backwards not supported! Last: " + str(current_last) + " New: " + str(head_block_num))
        self._service.insert_or_replace_entity(
            self._azure_config["status_table"],
            {"PartitionKey": "head_block_num",
             "RowKey": "last",
             "last_head_block_num": head_block_num})
