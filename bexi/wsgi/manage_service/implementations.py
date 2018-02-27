""" This module collects all business logic that is used in the routes of the corresponding blueprint
    in :mod:`.views`.
"""

import datetime

from bitshares.account import Account
from bitshares.amount import Amount
from bitshares.memo import Memo
from bitsharesbase import operations
from bitshares.transactionbuilder import TransactionBuilder
from bitshares.exceptions import AccountDoesNotExistsException

from ...addresses import (
    split_unique_address,
    get_from_address_from_operation,
    create_memo,
    get_to_address_from_operation)

from ...connection import requires_blockchain
from ... import Config, factory
from ... import utils
from ...operation_storage import operation_formatter
from ...wsgi import flask_setup


operation_storage = None


def _get_os(storage=None):
    global operation_storage
    if storage:
        operation_storage = storage

    if not operation_storage:
        operation_storage = factory.get_operation_storage()

    return operation_storage


def get_all_assets(take, continuation):
    take = int(take)
    start = int(continuation)
    end = start + take

    all_assets_config = Config.get_bitshares_config()["assets"]
    all_assets = []
    for i in range(start, end):
        if i < len(all_assets_config):
            all_assets.append(
                get_asset(all_assets_config[i]["asset_id"])
            )

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


@requires_blockchain
def validate_address(address, bitshares_instance=None):
    try:
        Account(split_unique_address(address)["account_id"], bitshares_instance=bitshares_instance)
        valid = True
    except AccountDoesNotExistsException:
        valid = False
    return {"isValid": valid}


def observe_address(address):
    _get_os().track_balance(address)


def unobserve_address(address):
    _get_os().untrack_balance(address)


def get_balances(take, continuation):
    balancesDict = _get_os().get_balances()

    take = int(take)
    try:
        start = int(continuation)
        if start != 0:
            raise Exception("Ensure sorting of the balances within operation storage first")
    except TypeError:
        start = 0
    end = start + take

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

    max_end = max(end, len(all_balances))

    return {
        "continuation": end if end < len(all_balances) else None,
        "items": all_balances[start:max_end]
    }


def get_address_history_from(address, take, after_hash):
    all_operations = []

    address = split_unique_address(address)
    afterTimestamp = datetime.datetime.fromtimestamp(0)
    for operation in _get_os().get_operations_completed(
            filter_by={"customer_id": address["customer_id"]}):
        # deposit, thus from
        if utils.is_exchange_account(operation["to"]):
            all_operations.append({
                "operationId": operation["incident_id"],
                "timestamp": operation["timestamp"],
                "fromAddress": get_from_address_from_operation(operation),
                "toAddress": get_to_address_from_operation(operation),
                "assetId": operation["amount_asset_id"],
                "amount": operation["amount_value"],
                "hash": operation["chain_identifier"]
            })
            if operation["chain_identifier"] == after_hash:
                afterTimestamp = utils.string_to_date(operation["timestamp"])

    older = [op for op in all_operations if
             afterTimestamp <=
             utils.string_to_date(op["timestamp"])]
    older.sort(key=lambda x: utils.string_to_date(x["timestamp"]))

    max_end = max(take, len(older))

    return older[0:max_end]


def get_address_history_to(address, take, after_hash):
    all_operations = []

    address = split_unique_address(address)
    afterTimestamp = datetime.datetime.fromtimestamp(0)
    for operation in _get_os().get_operations_completed(
            filter_by={"customer_id": address["customer_id"]}):
        # deposit, thus from
        if utils.is_exchange_account(operation["from"]):
            all_operations.append({
                "operationId": operation["incident_id"],
                "timestamp": operation["timestamp"],
                "fromAddress": get_from_address_from_operation(operation),
                "toAddress": get_to_address_from_operation(operation),
                "assetId": operation["amount_asset_id"],
                "amount": operation["amount_value"],
                "hash": operation["chain_identifier"]
            })
            if operation["chain_identifier"] == after_hash:
                afterTimestamp = utils.string_to_date(operation["timestamp"])

    older = [op for op in all_operations if
             afterTimestamp <=
             utils.string_to_date(op["timestamp"])]
    older.sort(key=lambda x: utils.string_to_date(x["timestamp"]))

    max_end = max(take, len(older))

    return older[0:max_end]


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
            60 * 30  # 30 mins
        )

        # Build the transaction, obtain fee to be paid
        tx.constructTx()
        return tx.json()

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

    if utils.is_exchange_account(from_account["id"]):
        # Withdrawal
        memo_plain = create_memo(toAddress, incidentId)
    elif utils.is_exchange_account(to_account["id"]):
        # Deposit
        memo_plain = create_memo(toAddress, incidentId)
    else:
        raise

    # Construct amount
    amount = Amount(
        {
            "amount": amount,
            "asset_id": asset_id
        },
        bitshares_instance=bitshares_instance
    )

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

    return {"transactionContext": tx}


@requires_blockchain
def broadcast_transaction(signed_transaction, bitshares_instance=None):
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

    if from_account != to_account:
        try:
            tx = tx.broadcast()
            return True
        except Exception as e:
            for op_in_tx, operation in enumerate(tx.get("operations", [])):
                storage.flag_operation_failed(map_operation(tx, op_in_tx, operation),
                                              str(e))
            return False
    else:
        # This happens in case of virtual consolidation transactions/transfers
        for op_in_tx, operation in enumerate(tx.get("operations", [])):
            op = map_operation(tx, op_in_tx, operation)
            op["block_num"] = -1
            storage.flag_operation_completed(op)
        return True


def get_broadcasted_transaction(operationId):
    operation = _get_os().get_operation(operationId)

    r_op = {
        "operationId": operation["incident_id"],
        "state": operation["status"],
        "timestamp": operation["timestamp"],
        "amount": operation["amount_value"],
        "fee": operation["fee"]["amount"],
        "hash": operation["chain_identifier"],
        "block": operation["block_num"],
    }
    if r_op["state"] == "failed":
        r_op["error"] = "An error occured while broadcasting the transaction"
        r_op["errorCode"] = "unknown"

    return r_op


def delete_broadcasted_transaction(operationId):
    _get_os().delete_operation(operationId)
