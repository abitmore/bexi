""" This module collects all business logic that is used in the routes of the corresponding blueprint
    in :mod:`.views`.
"""

from datetime import datetime
from flask import json

from bitshares.account import Account
from bitshares.amount import Amount
from bitshares.memo import Memo
from bitsharesbase import operations
from bitshares.transactionbuilder import TransactionBuilder
from bitshares.exceptions import AccountDoesNotExistsException,\
    AssetDoesNotExistsException

from ...addresses import (
    split_unique_address,
    get_from_address_from_operation,
    create_memo,
    get_to_address_from_operation)

from ...connection import requires_blockchain
from ... import Config, factory
from ... import utils
from ...operation_storage import operation_formatter
from bitsharesapi.exceptions import UnhandledRPCError
import time
from graphenebase import transactions


operation_storage = None


def _get_os(storage=None):
    global operation_storage
    if storage:
        operation_storage = storage

    if not operation_storage:
        operation_storage = factory.get_operation_storage()

    return operation_storage


def get_all_assets(take, continuation=0):
    take = take
    start = continuation
    end = start + take

    all_assets_config = Config.get_bitshares_config()["assets"]
    all_assets = []
    for i in range(start, end):
        if i < len(all_assets_config):
            all_assets.append(
                get_asset(all_assets_config[i]["asset_id"])
            )

    if start > len(all_assets_config):
        raise BadArgumentException()

    return {
        "continuation": end if end < len(all_assets_config) else None,
        "items": all_assets
    }


class AssetNotFoundException(Exception):
    pass


class AmountTooSmallException(Exception):
    pass


class NotEnoughBalanceException(Exception):
    pass


class BadArgumentException(Exception):
    pass


class TransactionExpiredException(Exception):
    pass


def get_asset(assetId):
        all_assets = Config.get_bitshares_config()["assets"]
        for asset in all_assets:
            if asset["asset_id"] == assetId:
                return {
                    "assetId": asset["asset_id"],
                    "address": asset["address"],
                    "name": asset["name"],
                    "accuracy": asset["accuracy"]
                }
        raise AssetNotFoundException()


def validate_address(address):
    return {"isValid": is_valid_address(address)}


@requires_blockchain
def is_valid_address(address, bitshares_instance=None):
    try:
        split = split_unique_address(address)
        if split.get("customer_id") is None:
            return False
        else:
            Account(split["account_id"], bitshares_instance=bitshares_instance)
            return True
    except Exception:
        return False


def observe_address(address):
    if is_valid_address(address):
        _get_os().track_address(address, "balance")
    else:
        raise AccountDoesNotExistsException()


def unobserve_address(address):
    if is_valid_address(address):
        _get_os().untrack_address(address, "balance")
    else:
        raise AccountDoesNotExistsException()


def get_balances(take, continuation=0):
    take = take
    start = continuation
    end = start + take

    balancesDict = _get_os().get_balances()

    all_accounts = sorted(balancesDict.keys())
    all_balances = []
    for account in all_accounts:
        for asset_id in balancesDict[account].keys():
            if balancesDict[account][asset_id] > 0:
                all_balances.append(
                    {
                        "address": account,
                        "assetId": asset_id,
                        "balance": balancesDict[account][asset_id],
                        "block": _get_os().get_last_head_block_num()
                    }
                )

    if start > len(all_balances):
        raise BadArgumentException()

    max_end = max(end, len(all_balances))

    return {
        "continuation": end if end < len(all_balances) else None,
        "items": all_balances[start:max_end]
    }


def get_address_history_from(address, take, after_hash=None):
    return _get_from_history(address, take, "from", after_hash)


def _get_from_history(address, take, to_or_from, after_hash=None):
    if not is_valid_address(address):
        raise AccountDoesNotExistsException()

    take = int(take)

    all_operations = []

    address = split_unique_address(address)
    afterTimestamp = datetime.fromtimestamp(0)
    for operation in _get_os().get_operations_completed(
            filter_by={"customer_id": address["customer_id"]}):
        # deposit, thus from
        if utils.is_exchange_account(operation[to_or_from]):
            add_op = {
                "operationId": operation.get("incident_id", None),
                "timestamp": operation.get("timestamp", None),
                "fromAddress": get_from_address_from_operation(operation),
                "toAddress": get_to_address_from_operation(operation),
                "assetId": operation["amount_asset_id"],
                "amount": str(operation["amount_value"]),
                "hash": operation["chain_identifier"]
            }
            all_operations.append(add_op)
            if operation["chain_identifier"] == after_hash and add_op["timestamp"]:
                afterTimestamp = utils.string_to_date(add_op["timestamp"])

    older = [op for op in all_operations if
             op["timestamp"] and afterTimestamp <=
             utils.string_to_date(op["timestamp"])]
    older.sort(key=lambda x: utils.string_to_date(x["timestamp"]))

    max_end = max(take, len(older))

    return older[0:max_end]


def get_address_history_to(address, take, after_hash=None):
    return _get_from_history(address, take, "to", after_hash)


@requires_blockchain
def build_transaction(incidentId, fromAddress, fromMemoWif, toAddress, asset_id,
                      amount, includeFee, bitshares_instance=None):
    """ Builds a transaction (without signature)

        :param guid operationId: Lykke unique operation ID
        :param str fromAddress: Source address
        :param str toAddress: Destination address
        :param str assetId: Asset ID to transfer
        :param str amount: Amount to transfer. Integer as string, aligned to the asset
                accuracy. Actual value can be calculated as x = amount / (10 ^
                asset.Accuracy)
        :param bool includeFee: Flag, which indicates, that the fee should
                be included in the specified amount
    """

    def obtain_raw_tx():
        op = operations.Transfer(**{
            "fee": {
                "amount": 0,
                "asset_id": "1.3.0"
            },  # will be replaced
            "from": from_account["id"],
            "to": to_account["id"],
            "amount": amount.json(),
            "memo": memo.encrypt(memo_plain),
            "prefix": bitshares_instance.prefix
        })

        tx = TransactionBuilder(
            bitshares_instance=bitshares_instance
        )
        tx.appendOps(op)
        tx.set_expiration(
            Config.get("bitshares", "transaction_expiration_in_sec", 60 * 60 * 24)  # 24 hours
        )

        # Build the transaction, obtain fee to be paid
        tx.constructTx()
        return tx.json()

    if not is_valid_address(fromAddress):
        raise AccountDoesNotExistsException()

    if not is_valid_address(toAddress):
        raise AccountDoesNotExistsException()

    # Decode addresses
    from_address = split_unique_address(fromAddress)
    to_address = split_unique_address(toAddress)

    # obtain chain accounts from addresses
    from_account = Account(
        from_address["account_id"],
        bitshares_instance=bitshares_instance)
    to_account = Account(
        to_address["account_id"],
        bitshares_instance=bitshares_instance)

    if utils.is_exchange_account(from_account["id"]) and utils.is_exchange_account(to_account["id"]):
        # internal shift
        memo_plain = create_memo(fromAddress, incidentId)
    elif utils.is_exchange_account(from_account["id"]):
        # Withdrawal
        memo_plain = create_memo(fromAddress, incidentId)
    elif utils.is_exchange_account(to_account["id"]):
        # Deposit
        memo_plain = create_memo(toAddress, incidentId)
    else:
        raise

    try:
        # Construct amount
        amount = Amount(
            {
                "amount": amount,
                "asset_id": asset_id
            },
            bitshares_instance=bitshares_instance
        )
    except AssetDoesNotExistsException:
        raise AssetNotFoundException()

    # encrypt memo
    # TODO this is a hack. python-bitshares issue is opened, once resolve, fix
    if not fromMemoWif:
        if from_address["account_id"] == Config.get("bitshares", "exchange_account_id"):
            fromMemoWif = Config.get("bitshares", "exchange_account_memo_key")

    if fromMemoWif:
        bitshares_instance.wallet.setKeys(fromMemoWif)

    memo = Memo(
        from_account=from_account,
        to_account=to_account,
        bitshares_instance=bitshares_instance
    )
    tx = obtain_raw_tx()

    fee = Amount(tx["operations"][0][1]["fee"],
                 bitshares_instance=bitshares_instance)
    if includeFee:
        # Reduce fee from amount to transfer
        amount -= fee
        tx = obtain_raw_tx()

    # Add additional/optional information
    tx.update({
        "decoded_memo": memo_plain,
    })

    if bitshares_instance.prefix != "BTS":
        tx["prefix"] = bitshares_instance.prefix

    return {"transactionContext": json.dumps(tx)}


@requires_blockchain
def broadcast_transaction(signed_transaction, bitshares_instance=None):
    if type(signed_transaction) == str:
        signed_transaction = json.loads(signed_transaction)

    tx = TransactionBuilder(
        signed_transaction,
        bitshares_instance=bitshares_instance
    )

    # Only broadcast if case 2 || 3
    assert len(tx.json()["operations"]) == 1, "Only one op per transaction allowed"
    from_account = tx.json()["operations"][0][1]["from"]
    to_account = tx.json()["operations"][0][1]["to"]

    # insert all transactions into storage
    storage = _get_os()

    def map_operation(tx, op_in_tx, operation):
        assert operation[0] == 0, "We only deal with transfers!"
        j = dict(
            op=operation,
            decoded_memo=tx["decoded_memo"],
            expiration=tx["expiration"],
            op_in_tx=op_in_tx,
            transaction_id=tx["transaction_id"]
        )
        return operation_formatter.decode_operation(j)

    for op_in_tx, operation in enumerate(tx.get("operations", [])):
        storage.insert_operation(map_operation(tx, op_in_tx, operation))

    exception_occured = None
    try:
        # check validity
        tx.verify_authority()
    except Exception as e:
        exception_occured = e

    if exception_occured is None and from_account != to_account:
        try:
            tx = tx.broadcast()
            if tx.get("id", None):
                return {"chain_identifier": tx["id"] + ":" + str(tx["trx_num"]), "block_num": tx["block_num"]}
            else:
                return {"chain_identifier": "no_id_given", "block_num": -1}
        except UnhandledRPCError as e:
            if "insufficient_balance" in str(e):
                raise NotEnoughBalanceException()
            elif "amount.amount > 0" in str(e):
                raise AmountTooSmallException()
            elif "now <= trx.expiration" in str(e):
                raise TransactionExpiredException()
            else:
                raise e
        except Exception as e:
            exception_occured = e

    if exception_occured:
        # this operation might not exist
        for op_in_tx, operation in enumerate(tx.get("operations", [])):
            storage.flag_operation_failed(map_operation(tx, op_in_tx, operation),
                                          str(exception_occured))
        raise exception_occured

    if from_account == to_account:
        # This happens in case of virtual consolidation transactions/transfers
        for op_in_tx, operation in enumerate(tx.get("operations", [])):
            op = map_operation(tx, op_in_tx, operation)
            op["block_num"] = -1
            storage.flag_operation_completed(op)
        return {"chain_identifier": "virtual_transfer", "block_num": op["block_num"]}
    else:
        raise Exception("This should be unreachable")


def get_broadcasted_transaction(operationId):
    operation = _get_os().get_operation(operationId)

    r_op = {
        "operationId": operation["incident_id"],
        "state": operation["status"],
        "timestamp": operation["timestamp"],
        "amount": str(operation["amount_value"]),
        "fee": str(operation["fee_value"]),
        "hash": operation["chain_identifier"]
    }
    if r_op["state"] == "failed":
        r_op["error"] = "An error occured while broadcasting the transaction"
        r_op["errorCode"] = operation["message"]

    if r_op["state"] == "completed":
        r_op["block"] = operation["block_num"]

    return r_op


def delete_broadcasted_transaction(operationId):
    _get_os().delete_operation(operationId)


def observe_address_history_from(address, track):
    if is_valid_address(address):
        if track:
            _get_os().track_address(address, "history_from")
        else:
            _get_os().untrack_address(address, "history_from")
    else:
        raise AccountDoesNotExistsException()


def observe_address_history_to(address, track):
    if is_valid_address(address):
        if track:
            _get_os().track_address(address, "history_to")
        else:
            _get_os().untrack_address(address, "history_to")
    else:
        raise AccountDoesNotExistsException()


