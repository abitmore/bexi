import time
import collections
from azure.common import AzureConflictHttpError, AzureMissingResourceHttpError,\
    AzureHttpError
from azure.cosmosdb.table.tableservice import TableService
from urllib3.exceptions import NewConnectionError

from ..addresses import split_unique_address, get_tracking_address, ensure_address_format
from .exceptions import (
    BalanceConcurrentException,
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
import hashlib
import zlib
import logging
from bitshares.amount import Amount


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
        return (NewConnectionError, AzureHttpError)

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
        self._operation_varients = ["incident", "statuscompleted", "statusfailed", "statusinprogress"]  #  "customer"
        self._operation_tables = {}
        for variant in self._operation_varients:
            self._operation_tables[variant] = self._azure_config["operation_table"] + variant

        self._operation_prep = {
            "statusinprogress": lambda op: {
                "PartitionKey": self._short_digit_hash(op["chain_identifier"]),
                "RowKey": op["chain_identifier"]
            },
            "statuscompleted": lambda op: {
                "PartitionKey": self._short_digit_hash(op["chain_identifier"]),
                "RowKey": op["chain_identifier"]
            },
            "statusfailed": lambda op: {
                "PartitionKey": self._short_digit_hash(op["chain_identifier"]),
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
        hash_type = Config.get("operation_storage", "key_hash", "type", default="crc32")

        if hash_type == "crc32":
            short_hash = hex(zlib.crc32(value.encode(encoding='UTF-8')))
            short_hash = short_hash[2:len(short_hash)]

        elif hash_type == "sha256":
            checker = hashlib.sha256()
            checker.update(value.encode(encoding='UTF-8'))
            short_hash = checker.hexdigest()
        return short_hash[0:Config.get("operation_storage", "key_hash", "digits", 3)]

    @retry_auto_reconnect
    def track_address(self, address, usage="balance"):
        address = ensure_address_format(address)
        try:
            short_hash = self._short_digit_hash(address)
            logging.getLogger(__name__).debug("track_address with " + str(address) + ", hash " + str(short_hash))
            self._service.insert_entity(
                self._azure_config["address_table"] + usage,
                {"PartitionKey": short_hash,
                 "RowKey": address,
                 "address": address,
                 "usage": usage}
            )
        except AzureConflictHttpError:
            raise AddressAlreadyTrackedException

    @retry_auto_reconnect
    def untrack_address(self, address, usage="balance"):
        address = ensure_address_format(address)
        try:
            short_hash = self._short_digit_hash(address)
            logging.getLogger(__name__).debug("untrack_address with " + str(address) + ", hash " + str(short_hash))
            self._service.delete_entity(
                self._azure_config["address_table"] + usage,
                short_hash,
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
            short_hash = self._short_digit_hash(address)
            logging.getLogger(__name__).debug("_get_address with " + str(address) + ", hash " + str(short_hash))
            return self._service.get_entity(
                self._azure_config["address_table"] + usage,
                short_hash,
                address)
        except AzureMissingResourceHttpError:
            raise AddressNotTrackedException()

    def _update(self, operation, status=None):
        try:
            mapping = {"in_progress": "statusinprogress",
                       "completed": "statuscompleted",
                       "failed": "statusfailed"}

            operation = self._get_with_ck("incident", operation.copy())
            new_operation = operation
            if status:
                tmp = self.get_operation(operation["incident_id"])
                new_operation["timestamp"] = tmp["timestamp"]
                new_operation["status"] = status
                new_operation = self._get_with_ck("incident", new_operation)

            logging.getLogger(__name__).debug("_update: Table " + self._operation_tables["incident"] + " PartitionKey " + new_operation["PartitionKey"] + " " + new_operation["RowKey"])

            self._service.update_entity(
                self._operation_tables["incident"],
                new_operation)

            operation = self._get_with_ck("statuscompleted", operation.copy())
            new_operation = operation
            if status:
                tmp = self.get_operation(operation["incident_id"])
                new_operation["timestamp"] = tmp["timestamp"]
                new_operation["status"] = status
                new_operation = self._get_with_ck("statuscompleted", new_operation)
            self._service.update_entity(
                self._operation_tables["statuscompleted"],
                new_operation)

            logging.getLogger(__name__).debug("_update: Table " + self._operation_tables["statuscompleted"] + " PartitionKey " + new_operation["PartitionKey"] + " " + new_operation["RowKey"])

            if status:
                # needs delete and insert
                try:
                    self._service.delete_entity(
                        self._operation_tables[mapping[operation["status"]]],
                        operation["PartitionKey"],
                        operation["RowKey"])
                except AzureMissingResourceHttpError:
                    pass
                try:
                    self._service.insert_entity(
                        self._operation_tables[mapping[new_operation["status"]]],
                        new_operation)
                except AzureConflictHttpError:
                    # already exists, try update
                    self._service.update_entity(
                        self._operation_tables[mapping[new_operation["status"]]],
                        new_operation)
            else:
                self._service.update_entity(
                    self._operation_tables[mapping[new_operation["status"]]],
                    new_operation)
        except AzureMissingResourceHttpError:
            raise OperationNotFoundException()

    def _insert(self, operation):
        try:
            for variant in self._operation_varients:
                to_insert = operation.copy()
                to_insert.update(self._operation_prep[variant](to_insert))
                if not to_insert["PartitionKey"]:
                    raise AzureMissingResourceHttpError()
                if not to_insert["RowKey"]:
                    raise AzureMissingResourceHttpError()

                logging.getLogger(__name__).debug("_insert: Table " + self._operation_tables[variant] + " PartitionKey " + to_insert["PartitionKey"] + " " + to_insert["RowKey"])
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

        error = None
        try:
            self._insert(operation)
        except DuplicateOperationException as e:
            error = e

        try:
            # always check if balances are ok
            if operation["status"] == "completed":
                self._ensure_balances(operation)
        except BalanceConcurrentException as e:
            if error is None:
                error = e

        if error is not None:
            raise error

    @retry_auto_reconnect
    def _delete_balance(self, address, if_match='*'):
        self._service.delete_entity(
            self._azure_config["balances_table"],
            self._short_digit_hash(address),
            address,
            if_match=if_match
        )

    @retry_auto_reconnect
    def _ensure_balances(self, operation):
        affected_address = get_tracking_address(operation)
        logging.getLogger(__name__).debug("_ensure_balances: with " + operation["chain_identifier"] + " for address " + str(affected_address))
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
            balance_dict["PartitionKey"] = self._short_digit_hash(balance_dict["address"])
            balance_dict["RowKey"] = balance_dict["address"]
            insert = True

        if operation["block_num"] < balance_dict.get("blocknum", 0):
            raise BalanceConcurrentException()
        elif operation["block_num"] == balance_dict.get("blocknum", 0) and\
                operation["txnum"] < balance_dict.get("txnum", 0):
            raise BalanceConcurrentException()
        elif operation["block_num"] == balance_dict.get("blocknum", 0) and\
                operation["txnum"] == balance_dict.get("txnum", 0) and\
                operation["opnum"] <= balance_dict.get("opnum", 0):
            raise BalanceConcurrentException()

        balance_dict["blocknum"] = max(balance_dict.get("blocknum", 0), operation["block_num"])
        balance_dict["txnum"] = max(balance_dict.get("txnum", 0), operation["tx_in_block"])
        balance_dict["opnum"] = max(balance_dict.get("opnum", 0), operation["op_in_tx"])
        total = 0

        addrs = split_unique_address(affected_address)

        asset_id_key = "balance" + operation["amount_asset_id"].split("1.3.")[1]
        asset_id = operation["amount_asset_id"]
        balance = Amount({
            "asset_id": asset_id,
            "amount": balance_dict.get(asset_id_key, "0")})
        amount_value = Amount({
            "asset_id": asset_id,
            "amount": operation["amount_value"]})

        if addrs["account_id"] == operation["from"]:
            # internal transfer and withdraw

            # negative
            balance_dict[asset_id_key] = str(int(balance - amount_value))

            # fee as well
            asset_id_key = "balance" + operation["fee_asset_id"].split("1.3.")[1]
            asset_id = operation["fee_asset_id"]
            balance = Amount({
                "asset_id": asset_id,
                "amount": balance_dict.get(asset_id_key, "0")})
            fee_value = Amount({
                "asset_id": asset_id,
                "amount": operation["fee_value"]})

            balance_dict[asset_id_key] = str(int(balance - fee_value))
        elif addrs["account_id"] == operation["to"]:
            # deposit

            # positive
            balance_dict[asset_id_key] = str(int(balance + amount_value))

            # fees were paid by someone else
        else:
            raise InvalidOperationException()

        for key, value in balance_dict.items():
            if key.startswith("balance"):
                total = total + int(value)

        if total == 0:
            if not insert:
                try:
                    self._delete_balance(affected_address,
                                         if_match=balance_dict.etag)
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
                    balance_dict,
                    if_match=balance_dict.etag
                )
            except AzureConflictHttpError:
                raise OperationStorageException("Critical error in database consistency")

    @retry_auto_reconnect
    def insert_or_update_operation(self, operation):
        # do basics
        operation = super(AzureOperationsStorage, self).insert_operation(operation)

        # check if this is from in_progress to complete (for withdrawals we need to find incident id as its
        # not stored onchain)
        try:
            logging.getLogger(__name__).debug("insert_or_update_operation: check if in_progress with " + str(operation["chain_identifier"]) + " exists")
            existing_operation = self.get_operation_by_chain_identifier("in_progress", operation["chain_identifier"])
            logging.getLogger(__name__).debug("insert_or_update_operation: found existing in_progress operation")
            if not existing_operation["incident_id"] == operation["incident_id"] and\
                    operation["incident_id"] == operation["chain_identifier"]:
                logging.getLogger(__name__).debug("insert_or_update_operation: using preset incident_id " + str(existing_operation["incident_id"]))
                operation["incident_id"] = existing_operation["incident_id"]
        except OperationNotFoundException:
            existing_operation = None

        if existing_operation is None:
            try:
                logging.getLogger(__name__).debug("insert_or_update_operation: attempting insert")

                error = None
                try:
                    self._insert(operation)
                except DuplicateOperationException as e:
                    error = e

                try:
                    # always check if balances are ok
                    if operation["status"] == "completed":
                        self._ensure_balances(operation)
                except BalanceConcurrentException as e:
                    if error is None:
                        error = e

                if error is not None:
                    raise error
            except DuplicateOperationException as ex:
                logging.getLogger(__name__).debug("insert_or_update_operation: fallback to update")
                # could be an update to completed ...
                if operation.get("block_num"):
                    try:
                        operation.pop("status")
                        self.flag_operation_completed(operation)
                    except OperationNotFoundException:
                        raise ex
                else:
                    raise ex
        else:
            logging.getLogger(__name__).debug("insert_or_update_operation: attempting update")
            if operation.get("block_num"):
                try:
                    operation.pop("status")
                    self.flag_operation_completed(operation)
                except OperationNotFoundException:
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
    def get_operation_by_chain_identifier(self, status, chain_identifier):
        mapping = {"in_progress": "statusinprogress",
                   "completed": "statuscompleted",
                   "failed": "statusfailed"}
        try:
            operation = self._service.get_entity(
                self._operation_tables[mapping[status]],
                self._short_digit_hash(chain_identifier),
                chain_identifier)
            operation.pop("PartitionKey")
            operation.pop("RowKey")
            operation.pop("Timestamp")
            operation.pop("etag")
        except AzureMissingResourceHttpError:
            raise OperationNotFoundException()
        return operation

    @retry_auto_reconnect
    def get_operation(self, incident_id):
        try:
            short_hash = self._short_digit_hash(incident_id)
            logging.getLogger(__name__).debug("get_operation with " + str(incident_id) + ", hash " + str(short_hash))
            operation = self._service.get_entity(
                self._operation_tables["incident"],
                short_hash,
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
                    continuation_marker = str(continuation_marker)
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
                    continuation_marker = str(continuation_marker)
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
        mapping = {"in_progress": "statusinprogress",
                   "completed": "statuscompleted",
                   "failed": "statusfailed"}

        filter_dict = {}
        filter_dict.update(self._parse_filter(filter_by))

        filter_str = self._filter_dict_to_string(filter_dict, "status")

        return list(self._service.query_entities(
            self._operation_tables[mapping["in_progress"]],
            filter_str))

    @retry_auto_reconnect
    def get_operations_completed(self, filter_by=None):
        mapping = {"in_progress": "statusinprogress",
                   "completed": "statuscompleted",
                   "failed": "statusfailed"}

        filter_dict = {}
        filter_dict.update(self._parse_filter(filter_by))

        filter_str = self._filter_dict_to_string(filter_dict, "status")

        return list(self._service.query_entities(
            self._operation_tables[mapping["completed"]],
            filter_str))

    @retry_auto_reconnect
    def get_operations_failed(self, filter_by=None):
        mapping = {"in_progress": "statusinprogress",
                   "completed": "statuscompleted",
                   "failed": "statusfailed"}

        filter_dict = {}
        filter_dict.update(self._parse_filter(filter_by))

        filter_str = self._filter_dict_to_string(filter_dict, "status")

        return list(self._service.query_entities(
            self._operation_tables[mapping["failed"]],
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
