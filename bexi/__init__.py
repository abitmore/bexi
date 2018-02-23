import os
import yaml
import logging
from logging.handlers import TimedRotatingFileHandler
from copy import deepcopy
import io
import urllib
import collections
import json


class Config(dict):
    """ This class allows us to load the configuration from a YAML encoded
        configuration file.
    """

    data = None

    @staticmethod
    def load(config_files=[]):
        """ Load config from a file

            :param str file_name: (defaults to 'config.yaml') File name and
                path to load config from
        """
        # single json configuration file to load instead of yaml files
        file_or_url = os.environ.get("SettingsUrl", None)

        if not Config.data:
            Config.data = {}

        if not file_or_url:
            if not config_files:
                config_files.append("config_bitshares_connection.yaml")
                config_files.append("config_bitshares_keys.yaml")
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
                    update(Config.data, yaml.load(stream))
        else:
            stream = urllib.request.urlopen(urllib.parse.urlparse(file_or_url).geturl())
            with stream:
                update(Config.data, json.loads(stream.read()))

        # check if a private key was given, and overwrite existing ones then
        private_key = os.environ.get("PrivateKey", None)
        if private_key and private_key != "":
            try:
                Config.data["bitshares"]["exchange_account_active_key"] = private_key
            except KeyError:
                pass
            try:
                all_connections = Config.data["bitshares"]["connection"]
                for key, value in all_connections.items():
                    try:
                        Config.data["bitshares"]["connection"][key]["keys"] = [private_key]
                    except KeyError:
                        pass
            except KeyError:
                pass

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
    def get_bitshares_config():
        return deepcopy(Config.get_config()["bitshares"])

    @staticmethod
    def reset():
        """ Static method to reset the configuration storage
        """
        Config.data = None

    @staticmethod
    def dump_current(file_name="config.json"):
        output = os.path.join(Config.get_config()["dump_folder"], file_name)
        with open(output, 'w') as outfile:
            json.dump(Config.data, outfile)


def update(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def set_global_logger():
    # setup logging
    # ... log to file system
    log_folder = os.path.join(Config.get_config()["dump_folder"], "logs")
    os.makedirs(log_folder, exist_ok=True)
    log_format = ('%(asctime)s %(levelname) -10s: %(message)s')
    trfh = TimedRotatingFileHandler(
        os.path.join(log_folder, "bexi.log"),
        "midnight",
        1
    )
    trfh.suffix = "%Y-%m-%d"
    trfh.setLevel(logging.DEBUG)
    trfh.setFormatter(logging.Formatter(log_format))

    # ... and to console
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(logging.Formatter(log_format))

    # global config (e.g. for werkzeug)
    logging.basicConfig(level=logging.DEBUG,
                        format=log_format,
                        handlers=[trfh, sh])

    return [trfh, sh]
