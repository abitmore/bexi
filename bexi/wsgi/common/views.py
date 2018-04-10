""" This module collects all routes that will be put into the common blueprint
"""

from flask import Blueprint
from flask import jsonify

from ... import Config, __VERSION__
from ...wsgi import flask_setup


blueprint_common = Blueprint('Common', __name__)
""" flask blueprint with all routes listed in here
"""


@blueprint_common.route('/api/isalive')
def isalive():
    """
        [GET] /api/isalive
    """
    info = {
        "name": Config.get("wsgi", "name"),
        "version": __VERSION__,
        "env": flask_setup.get_env_info(),
        "isDebug": flask_setup.is_debug_on(),
        "contractVersion": "1.1.3"}
    return jsonify(info)
