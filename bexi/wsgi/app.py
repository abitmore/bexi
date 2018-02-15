from flask import Flask

from . import flask_setup

from .. import set_global_logger
from .. import Config

from .common.views import blueprint_common
from .sign_service.views import blueprint_sign_service
from .manage_service.views import blueprint_manage_service

import pprint


def create_basic_flask_app():
    """
    Creates the basic app and sets the logger, no routes are set
    """
    app = Flask(__name__)
    # set app.logger for flask
    while len(app.logger.handlers) > 0:
        app.logger.removeHandler(app.logger.handlers[0])

    log_handlers = set_global_logger()
    for handler in log_handlers:
        app.logger.addHandler(handler)

#     app.logger.debug("Flask was initialized with ... \n" + pprint.pformat(Config.get_config()))

    return app


def create_common_app(app=None):
    """ Sets the routes defined by the common blueprint as defined in :mod:`.common.views`

        :param app: the flask app, will be created if not given
        :type app: object
    """
    if not app:
        app = create_basic_flask_app()

    flask_setup.setup_blueprint(blueprint_common)
    app.register_blueprint(blueprint_common)

    return app


def create_sign_service_app(app=None):
    """ Sets the routes defined by the sign service blueprint as defined in :mod:`.sign_service.views`

        :param app: the flask app, will be created if not given
        :type app: object
    """
    if not app:
        app = create_common_app(create_basic_flask_app())

    flask_setup.setup_blueprint(blueprint_sign_service)
    app.register_blueprint(blueprint_sign_service)

    return app


def create_manage_service_app(app=None):
    """ Sets the routes defined by the manage service blueprint as defined in :mod:`.manage_service.views`

        :param app: the flask app, will be created if not given
        :type app: object
    """
    if not app:
        app = create_common_app(create_basic_flask_app())

    flask_setup.setup_blueprint(blueprint_manage_service)
    app.register_blueprint(blueprint_manage_service)

    return app
