""" This module collects all routes that will be put into the manage service blueprint.
    Note that this module is intentionally just an encapsulation for the business logic that is
    put into :mod:`.implementations`.
"""

from flask import Blueprint, jsonify

from . import implementations


blueprint_blockchain_monitor_service = Blueprint("Blockchain.Monitor", __name__)
""" flask blueprint with all routes listed in here
"""


@blueprint_blockchain_monitor_service.route('/api/isalive')
def isalive():
    """
        [GET] /api/isalive
    """
    return jsonify(
        implementations.isalive()
    )
