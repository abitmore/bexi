import os
import yaml
import logging
from logging.handlers import TimedRotatingFileHandler
from copy import deepcopy
import io
import urllib


class Config(dict):
    """ This class allows us to load the configuration from a YAML encoded
        configuration file.
    """

    data = None

    @staticmethod
    def load():
        """ Load config from a file

            :param str file_name: (defaults to 'config.yaml') File name and
                path to load config from
        """
        file_or_url = os.environ.get("SettingsUrl", None)

        default = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "config.yaml"
        )
        if not file_or_url:
            file_or_url = default

        try:
            if os.path.isfile(file_or_url):
                stream = io.open(file_or_url, 'r', encoding='utf-8')
            else:
                stream = urllib.request.urlopen(urllib.parse.urlparse(file_or_url).geturl())
        except Exception as e:
            print("Something bad happened while loading config, returning to defaults ...")
            print(e)
            stream = io.open(default, 'r', encoding='utf-8')

        with stream:
            Config.data = yaml.load(stream)
        return Config.data

    @staticmethod
    def get_config():
        """ Static method that returns the configuration as dictionary.
            Usage:

            .. code-block:: python

                Config.get_config()
        """
        if not Config.data:
            Config.load()
        return Config(deepcopy(Config.data))

    @staticmethod
    def reset():
        """ Static method to reset the configuration storage
        """
        Config.data = None

    @staticmethod
    def get_bitshares_config():
        return Config.get_config()["bitshares"]


def set_global_logger():
    # setup logging
    # ... log to file system
    log_folder = Config.get_config()["log_folder"]
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
