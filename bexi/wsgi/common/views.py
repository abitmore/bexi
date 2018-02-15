""" This module collects all routes that will be put into the common blueprint
"""

from flask import Blueprint
from flask import jsonify

from ... import Config
from ...wsgi import flask_setup


blueprint_common = Blueprint('Common', __name__)
""" flask blueprint with all routes listed in here
"""


@blueprint_common.route('/api/isalive')
def isalive():
    """
        [GET] /api/isalive
    """
    config = Config.get_config()
    info = {
        "name": config["wsgi"]["name"],
        "version": config["wsgi"]["version"],
        "env": flask_setup.get_env_info(),
        "isDebug": flask_setup.is_debug_on()}
    return jsonify(info)
