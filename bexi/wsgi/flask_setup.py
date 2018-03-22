from flask import jsonify, current_app
from werkzeug.exceptions import HTTPException, InternalServerError
import os
import traceback

from .. import Config


def setup_blueprint(blueprint):
    """
    Configures the given blueprint.
     - sets the error handles to unify error response

    :param blueprint: blueprint to modify
    :type blueprint: flask.Blueprint

    """
    blueprint.errorhandler(Exception)(handle_exception)
    # In the case of an internal error after the user function
    # (e.g. a view does not return any value)
    # flask is looking for a specifically set InternalServerError handler,
    # see flask/app.py:handle_exception:1532
    blueprint.errorhandler(InternalServerError)(handle_exception)


class ErrorCodeException(Exception):
    """
        This exception is a Exception that can also be inputed with an error_code.
        This code will be returned in the error response
    """

    def __init__(self, http_status_code, error_code):
        self.error_code = error_code
        self.http_status_code = http_status_code


def custom_abort(http_status_code, error_code=None):
    if error_code:
        raise ErrorCodeException(http_status_code, error_code)
    else:
        raise ErrorCodeException(http_status_code, "unknown")


def get_error_response(ex):
    """ Returns a unified json object as reponse for the failed request.
        If the causing exception is a ErrorCodeException, the error_code is added
        to the reponse

        :param Exception ex: exception to be handled
        :rtype: dict
    """
    error_code = "unknown"
    if isinstance(ex, ErrorCodeException):
        error_code = ex.error_code

    if Config.get("wsgi", "detailed_error", True):
        message = ex.__class__.__name__ + "\n" + ''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__))
    else:
        message = str(ex)

    return {
        "errorMessage": message,
        "errorCode": error_code
    }


def handle_exception(e):
    """
    Creates the reposne for a failed request

    :param Exception e: exception to be handled
    :returns: HTTP response jsonified :func:'get_error_response'

    """
    code = 500
    if isinstance(e, ErrorCodeException):
        code = e.http_status_code
    resp = jsonify(get_error_response(e))
    resp.status_code = code
    current_app.logger.exception(e)
    return resp


def is_debug_on():
    """
    Determines whether this flask app runs in debug mode
    """
    return current_app.debug


def get_env_info():
    """
    Returns the environment variable ENV_INFO
    """
    # return ENV_INFO environment variable value
    return os.environ.get("ENV_INFO", None)

