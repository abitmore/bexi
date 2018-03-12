""" This module collects all routes that will be put into the manage service blueprint.
    Note that this module is intentionally just an encapsulation for the business logic that is
    put into :mod:`.implementations`.
"""

from flask import Blueprint, request
from flask import jsonify, abort

from . import implementations
import json
from json.decoder import JSONDecodeError


blueprint_sign_service = Blueprint("Blockchain.SignService", __name__)
""" flask blueprint with all routes listed in here
"""


def _body(parameter_name, default_value=None):
    lookup = request.get_json()
    if not lookup:
        if type(request.data) == bytes:
            lookup = json.loads(request.data)
    return lookup.get(parameter_name, default_value)


@blueprint_sign_service.route("/api/wallets", methods=["POST"])
def wallets():
    """
    [POST] /api/wallets
    """
    return jsonify(
        implementations.create_address()
    )


@blueprint_sign_service.route("/api/sign", methods=["POST"])
def sign():
    """
    [POST] /api/sign
    """
    try:
        return jsonify(
            implementations.sign(_body("transactionContext"), _body("privateKeys"))
        )
    except JSONDecodeError:
        abort(400)
