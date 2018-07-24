import pprint
import logging
from inspect import signature

from bitshares.instance import set_shared_bitshares_instance, SharedInstance
import bitshares
from . import Config


class Configured_Instance():
    configured_instance = None


def _ensure_blockchain_connection():
    """
    Checks if the SharedInstance.instance is the configured instance and if not
    initializes and sets it
    """
    if not Configured_Instance.configured_instance:
        Configured_Instance.configured_instance = _get_configured_instance()

    if SharedInstance.instance != Configured_Instance.configured_instance:
        set_shared_bitshares_instance(Configured_Instance.configured_instance)

    return Configured_Instance.configured_instance


def reset():
    Configured_Instance.configured_instance = None


def _get_configured_instance():
    network = Config.get("network_type")
    connection = Config.get("bitshares", "connection", network)
    if connection.get("num_retries", None) is None:
        connection["num_retries"] = -1
    logging.getLogger(__name__).debug("BitShares connection is initialized with with given config ... \n")
    return bitshares.BitShares(**connection)


def requires_blockchain(func):
    """
    This decorator allows lazy loading of the bitshares instance with the
    proper connection configuration.  Use this for every method that will use
    the bitshares shared instance
    """

    def ensure(*args, **kwargs):
        if "bitshares_instance" in kwargs:
            kwargs.update(dict(bitshares_instance=kwargs["bitshares_instance"]))
        else:
            # check if target functions wants instance
            add_instance = False
            try:
                sig = signature(func)
                sig.parameters["bitshares_instance"]
                add_instance = True
            except KeyError:
                pass
            bts = _ensure_blockchain_connection()
            if add_instance:
                kwargs.update(dict(bitshares_instance=bts))
        return func(*args, **kwargs)

    return ensure
