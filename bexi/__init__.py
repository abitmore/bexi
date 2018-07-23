import os
import yaml
import logging
from logging.handlers import TimedRotatingFileHandler, HTTPHandler
from copy import deepcopy
import io
import urllib.request
import collections
import json
import threading


def get_version():
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", 'VERSION')) as version_file:
        return version_file.read().strip()


__VERSION__ = get_version()


class Config(dict):
    """ This class allows us to load the configuration from a YAML encoded
        configuration file.
    """

    ERRORS = {}

    data = None
    source = None

    @staticmethod
    def load(config_files=[]):
        """ Load config from a file

            :param str file_name: (defaults to 'config.yaml') File name and
                path to load config from
        """

        # optional single json configuration file to load instead of yaml files
        file_or_url = os.environ.get("SettingsUrl", None)

        if not Config.data:
            Config.data = {}

        if not file_or_url:
            if not config_files:
                # load all config files as default
                config_files.append("config_bitshares_connection.yaml")
                config_files.append("config_bitshares_active_keys.yaml")
                config_files.append("config_bitshares_memo_keys.yaml")
                config_files.append("config_bitshares.yaml")
                config_files.append("config_operation_storage.yaml")
                config_files.append("config_common.yaml")
            if type(config_files) == str:
                config_files = [config_files]

            for config_file in config_files:
                file_path = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    config_file
                )
                stream = io.open(file_path, 'r', encoding='utf-8')
                with stream:
                    Config._nested_update(Config.data, yaml.load(stream))

            Config.source = ";".join(config_files)
        else:
            stream = urllib.request.urlopen(urllib.parse.urlparse(file_or_url).geturl())
            with stream:
                Config._nested_update(Config.data, json.loads(stream.read()))
            Config.source = file_or_url

        # check if a private key was given, and overwrite existing ones then
        private_key = os.environ.get("PrivateKey", None)
        if private_key and private_key != "":
            try:
                # direct access to config dict for overwriting
                Config.data["bitshares"]["exchange_account_active_key"] = private_key
            except KeyError:
                pass
#             try:
#                 all_connections = Config.data["bitshares"]["connection"]
#                 for key, value in all_connections.items():
#                     try:
#                         # direct access to config dict for overwriting
#                         keys = Config.data["bitshares"]["connection"][key]["keys"]
#                     except KeyError:
#                         keys = {}
#                     keys.append(private_key)
#                     Config.data["bitshares"]["connection"][key]["keys"] = keys
#             except KeyError:
#                 pass

    @staticmethod
    def get_config(config_name=None):
        """ Static method that returns the configuration as dictionary.
            Usage:

            .. code-block:: python

                Config.get_config()
        """
        if not config_name:
            if not Config.data:
                raise Exception("Either preload the configuration or specify config_name!")
        else:
            if not Config.data:
                Config.data = {}
            Config.load(config_name)
        return deepcopy(Config.data)

    @staticmethod
    def get(*args, message=None, default=None):
        """
        This config getter method allows sophisticated and encapsulated access to the config file, while
        being able to define defaults in-code where necessary.

        :param args: key to retrieve from config, nested in order. if the last is not a string it is assumed to be the default, but giving default keyword is then forbidden
        :type tuple of strings, last can be object
        :param message: message to be displayed when not found, defaults to entry in ERRORS dict with the
                                key defined by the desired config keys in args (key1.key2.key2). For example
                                Config.get("foo", "bar") will attempt to retrieve config["foo"]["bar"], and if
                                not found raise an exception with ERRORS["foo.bar"] message
        :type message: string
        :param default: default value if not found in config
        :type default: object
        """

        # check if last in args is default value
        if type(args[len(args) - 1]) != str:
            if default:
                raise KeyError("There can only be one default set. Either use default=value or add non-string values as last positioned argument!")
            default = args[len(args) - 1]
            args = args[0:len(args) - 1]

        try:
            nested = Config.data
            for key in args:
                if type(key) == str:
                    nested = nested[key]
                else:
                    raise KeyError("The given key " + str(key) + " is not valid.")
            if nested is None:
                raise KeyError()
        except KeyError:
            lookup_key = '.'.join(str(i) for i in args)
            if not message:
                if Config.ERRORS.get(lookup_key):
                    message = Config.ERRORS[lookup_key]
                else:
                    message = "Configuration key {0} not found in {1}!"
                message = message.format(lookup_key, Config.source)
            if default is not None:
                logging.getLogger(__name__).debug(message + " Using given default value.")
                return default
            else:
                raise KeyError(message)

        return nested

    @staticmethod
    def get_bitshares_config():
        return deepcopy(Config.get_config()["bitshares"])

    @staticmethod
    def reset():
        """ Static method to reset the configuration storage
        """
        Config.data = None
        Config.source = None

#     @staticmethod
#     def dump_current(file_name="config.json"):
#         output = os.path.join(Config.get_config()["dump_folder"], file_name)
#         with open(output, 'w') as outfile:
#             json.dump(Config.data, outfile)

    @staticmethod
    def _nested_update(d, u):
        for k, v in u.items():
            if isinstance(v, collections.Mapping):
                d[k] = Config._nested_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d


class LykkeHttpHandler(HTTPHandler):

    def mapLogRecord(self, record):
        from .wsgi import flask_setup

        record_dict = record.__dict__
        record_dict["appName"] = Config.get("wsgi", "name")
        record_dict["appVersion"] = __VERSION__
        record_dict["envInfo"] = flask_setup.get_env_info()
        record_dict["logLevel"] = record_dict["levelname"]
        record_dict["component"] = record_dict["name"]
        record_dict["process"] = record_dict["processName"]
        record_dict["context"] = None

        if record_dict.get("exc_info", None) is not None:
            record_dict["callStack"] = record_dict["exc_text"]
            record_dict["exceptionType"] = record_dict["exc_info"][0].__name__

        return record_dict

    def update_blocking(self):
        self.blocking = Config.get("logs", "http", "blocking", False)

    def emit(self, record):
        if self.blocking:
            super(LykkeHttpHandler, self).emit(record)
        else:
            def super_emit():
                super(LykkeHttpHandler, self).emit(record)

            thread = threading.Thread(target=super_emit)
            thread.daemon = True
            thread.start()


def set_global_logger(existing_loggers=None):
    use_handlers = []

    # setup logging
    log_level = logging.getLevelName(Config.get("logs", "level", default="INFO"))
    log_format = ('%(asctime)s %(levelname) -10s: %(message)s')

    if Config.get("logs", "file", True):
        # ... log to file system
        log_folder = os.path.join(Config.get("dump_folder", default="dump"), "logs")
        os.makedirs(log_folder, exist_ok=True)
        trfh = TimedRotatingFileHandler(
            os.path.join(log_folder, "bexi.log"),
            "midnight",
            1
        )
        trfh.suffix = "%Y-%m-%d"
        trfh.setFormatter(logging.Formatter(log_format))
        trfh.setLevel(log_level)

        use_handlers.append(trfh)

    # ... and to console
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter(log_format))
    sh.setLevel(log_level)

    use_handlers.append(sh)

    if not Config.get("logs", "http", {}) == {}:
        # ... and http logger
        lhh = LykkeHttpHandler(
            host=Config.get("logs", "http", "host"),
            url=Config.get("logs", "http", "url"),
            method="POST",
            secure=Config.get("logs", "http", "secure")
        )
        lhh.setLevel(log_level)
        lhh.update_blocking()
        use_handlers.append(lhh)

    # global config (e.g. for werkzeug)
    logging.basicConfig(level=log_level,
                        format=log_format,
                        handlers=use_handlers)

    if existing_loggers is not None:
        if not type(existing_loggers) == list:
            existing_loggers = [existing_loggers]
        for logger in existing_loggers:
            logger.setLevel(log_level)
            while len(logger.handlers) > 0:
                logger.removeHandler(logger.handlers[0])
            for handler in use_handlers:
                logger.addHandler(handler)

    return use_handlers


Config.load("config_common.yaml")
set_global_logger()
