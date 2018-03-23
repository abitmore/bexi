""" This module collects all routes that will be put into the manage service blueprint.
    Note that this module is intentionally just an encapsulation for the business logic that is
    put into :mod:`.implementations`.
"""

from flask import Blueprint, request, jsonify
import json
from bitshares.exceptions import AccountDoesNotExistsException
from json.decoder import JSONDecodeError

from . import implementations
from ..flask_setup import custom_abort
from ...operation_storage.interface import AddressAlreadyTrackedException,\
    AddressNotTrackedException, DuplicateOperationException,\
    OperationNotFoundException
from .implementations import AssetNotFoundException, NotEnoughBalanceException,\
    AmountTooSmallException, TransactionExpiredException


blueprint_manage_service = Blueprint("Blockchain.Api", __name__)
""" flask blueprint with all routes listed in here
"""


def _get(parameter_name, default_value=None):
    return request.args.get(parameter_name, default_value)


def _get_take():
    take = request.args.get("take", None)
    if not take:
        custom_abort(400)
    if type(take) != int and type(take) != str:
        custom_abort(400)
    try:
        return int(take)
    except ValueError:
        custom_abort(400)


def _get_continuation():
    # continuation is optional
    continuation = request.args.get("continuation", None)
    if continuation:
        if type(continuation) != int and type(continuation) != str:
            custom_abort(400)
        try:
            return int(continuation)
        except ValueError:
            custom_abort(400)
    else:
        return 0


def _body(parameter_name, default_value=None):
    try:
        lookup = request.get_json()
        if not lookup:
            if type(request.data) == bytes:
                lookup = json.loads(request.data)
        return lookup.get(parameter_name, default_value)
    except JSONDecodeError:
        custom_abort(400)


@blueprint_manage_service.route("/api/capabilities")
def get_capabilities():
    """
    [GET] /api/capabilities
    """
    return jsonify(
        {"isTransactionsRebuildingSupported": False,
         "areManyInputsSupported": False,
         "areManyOutputsSupported": False}
    )


@blueprint_manage_service.route("/api/assets")
def get_all_assets():
    """
    [GET] /api/assets?take=integer&[continuation=string]
    """
    try:
        return jsonify(
            implementations.get_all_assets(_get_take(), _get_continuation())
        )
    except ValueError:
        custom_abort(400)
    except BadArgumentException:
        custom_abort(400)


@blueprint_manage_service.route("/api/assets/<assetId>")
def get_asset(assetId):
    """
    [GET] /api/assets/{assetId}

    :param assetId: id of the wanted asset
    :type assetId: string
    :raises: 204 No content - specified asset not found

    """
    try:
        return jsonify(
            implementations.get_asset(assetId)
        )
    except AssetNotFoundException:
        # controlled abort, no logging
        return jsonify(data=[]), 204


@blueprint_manage_service.route("/api/addresses/<address>/validity", methods=["GET"])
def address_validity(address):
    """
    [GET] /api/addresses/{address}/validity

    :param address: address to be validated
    :type address: string

    """
    return jsonify(
        implementations.validate_address(address)
    )


@blueprint_manage_service.route("/api/balances/<address>/observation", methods=["POST"])
def observe_address(address):
    """
    [POST] /api/balances/{address}/observation

    :param address: address to be validated
    :type address: string
    :raises: 409 Conflict - specified address is already observed

    """
    try:
        return jsonify(
            implementations.observe_address(address)
        )
    except AddressAlreadyTrackedException:
        # controlled abort, no logging
        custom_abort(409)
    except AccountDoesNotExistsException:
        custom_abort(400)


@blueprint_manage_service.route("/api/balances/<address>/observation", methods=["DELETE"])
def unobserve_address(address):
    """
    [DELETE] /api/balances/{address}/observation

    :param address: address to be validated
    :type address: string
    :raises: 204 No content - specified address is not observed

    """
    try:
        return jsonify(
            implementations.unobserve_address(address)
        )
    except AddressNotTrackedException:
        # controlled abort, no logging
        return jsonify(data=[]), 204
    except AccountDoesNotExistsException:
        custom_abort(400)


@blueprint_manage_service.route("/api/balances", methods=["GET"])
def get_balances():
    """
    [GET] /api/balances?take=integer&[continuation=string]
    """
    try:
        return jsonify(
            implementations.get_balances(_get_take(), _get_continuation())
        )
    except BadArgumentException:
        custom_abort(400)


@blueprint_manage_service.route("/api/transactions/single", methods=["POST"])
def build_transaction():
    """
    [POST] /api/transactions

    :raises: 400 Bad Request - among other causes these specific error codes are distinguished:
                amountIsTooSmall - amount is too small to execute transaction
                notEnoughBalance - transaction can’t be executed due to balance insufficiency on the source address
                transactionExpired - transaction has already expired
                assetNotFound - desired asset could not be found

    """
    try:
        return jsonify(
            implementations.build_transaction(
                _body("operationId"),
                _body("fromAddress"),
                _body("fromAddressContext"),
                _body("toAddress"),
                _body("assetId"),
                _body("amount"),
                _body("includeFee")
            ))
    except AmountTooSmallException:
        custom_abort(400, "amountIsTooSmall")
    except NotEnoughBalanceException:
        custom_abort(400, "notEnoughBalance")
    except AssetNotFoundException:
        custom_abort(400, "assetNotFound")
    except AccountDoesNotExistsException:
        custom_abort(400)


@blueprint_manage_service.route("/api/transactions/broadcast", methods=["POST"])
def broadcast_transaction():
    """
    [POST] /api/transactions/broadcast

    :raises: 400 Bad Request - among other causes these specific error codes are distinguished:
                amountIsTooSmall - amount is too small to execute transaction
                notEnoughBalance - transaction can’t be executed due to balance insufficiency on the source address
    :raises: 409 Conflict - transaction with specified operationId and signedTransaction has already been broadcasted.

    """
    try:
        return jsonify(
            implementations.broadcast_transaction(_body("signedTransaction"))
        )
    except NotEnoughBalanceException:
        custom_abort(400, "notEnoughBalance")
    except DuplicateOperationException:
        custom_abort(409)
    except TransactionExpiredException:
        custom_abort(400, "transactionExpired")
    except JSONDecodeError:
        custom_abort(400)


@blueprint_manage_service.route("/api/transactions/broadcast/single/<operationId>", methods=["GET"])
def get_broadcasted_transaction(operationId):
    """
    [GET] /api/transactions/broadcast/{operationId}

    :raises 204 No content - specified transaction not found

    """
    try:
        return jsonify(
            implementations.get_broadcasted_transaction(operationId)
        )
    except OperationNotFoundException:
        # controlled abort, no logging
        return jsonify(data=[]), 204


@blueprint_manage_service.route("/api/transactions/broadcast", methods=["DELETE"])
@blueprint_manage_service.route("/api/transactions/broadcast/<operationId>", methods=["DELETE"])
def delete_broadcasted_transaction(operationId=None):
    """
    [DELETE] /api/transactions/broadcast/{operationId}

    :raises 204 No content - specified transaction not found

    """
    try:
        if not operationId:
            custom_abort(500)
        return jsonify(
            implementations.delete_broadcasted_transaction(operationId)
        )
    except OperationNotFoundException:
        # controlled abort, no logging
        return jsonify(data=[]), 204


@blueprint_manage_service.route("/api/transactions/history/from/<address>/observation", methods=["POST"])
def observe_address_history_from(address):
    """
    [POST] /api/transactions/history/from/{address}/observation

    :param address: the address whose history should be observed
    :type address: string
    :raises 409 Conflict: transactions from the address are already observed.

    """
    try:
        return jsonify(
            implementations.observe_address_history_from(address, True)
        )
    except AccountDoesNotExistsException:
        custom_abort(400)
    except AddressAlreadyTrackedException:
        custom_abort(409)


@blueprint_manage_service.route("/api/transactions/history/from/<address>/observation", methods=["DELETE"])
def unobserve_address_history_from(address):
    """
    [DELETE] /api/transactions/history/from/{address}/observation

    :param address: the address whose history should be deleted
    :type address: string
    :raises 204 No content: transactions from the address are not observed.

    """
    try:
        return jsonify(
            implementations.observe_address_history_from(address, False)
        )
    except AccountDoesNotExistsException:
        custom_abort(400)
    except AddressNotTrackedException:
        return jsonify(data=[]), 204


@blueprint_manage_service.route("/api/transactions/history/to/<address>/observation", methods=["POST"])
def observe_address_history_to(address):
    """
    [POST] /api/transactions/history/to/{address}/observation

    :param address: the address whose history should be observed
    :type address: string
    :raises 409 Conflict: transactions from the address are already observed.

    """
    try:
        return jsonify(
            implementations.observe_address_history_to(address, True)
        )
    except AccountDoesNotExistsException:
        custom_abort(400)
    except AddressAlreadyTrackedException:
        custom_abort(409)


@blueprint_manage_service.route("/api/transactions/history/to/<address>/observation", methods=["DELETE"])
def unobserve_address_history_to(address):
    """
    [DELETE] /api/transactions/history/to/{address}/observation

    :param address: the address whose history should be observed
    :type address: string
    :raises 204 No content: transactions from the address are not observed.

    """
    try:
        return jsonify(
            implementations.observe_address_history_to(address, False)
        )
    except AccountDoesNotExistsException:
        custom_abort(400)
    except AddressNotTrackedException:
        return jsonify(data=[]), 204


@blueprint_manage_service.route("/api/transactions/history/from/<address>", methods=["GET"])
def get_address_history_from(address):
    """
    [GET] /api/transactions/history/from/{address}?take=integer&[afterHash=string]

    :param address: the address whose history should be observed
    :type address: string

    """
    return jsonify(
        implementations.get_address_history_from(address, _get_take(), _get("afterHash"))
    )


@blueprint_manage_service.route("/api/transactions/history/to/<address>", methods=["GET"])
def get_address_history_to(address):
    """
    [GET] /api/transactions/history/to/{address}/?take=integer&[afterHash=string]

    :param address: the address whose history shou8ld be observed
    :type address: string

    """
    return jsonify(
        implementations.get_address_history_to(address, _get_take(), _get("afterHash"))
    )
