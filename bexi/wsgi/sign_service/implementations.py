""" This module collects all business logic that is used in the routes of the corresponding blueprint
    in :mod:`.views`.
"""

from ... import Config
from ...transaction_signer import sign_transaction
from ...addresses import create_unique_address


def sign(tx, keys):
    """ This method is used to connect the transaction signer with the API.
    """
    if keys[0] == "keep_keys_private" and Config.get("bitshares", "keep_keys_private", True):
        keys = [Config.get("bitshares", "exchange_account_active_key")]

    signedTransaction = sign_transaction(tx, keys)
    try:
        signedTransaction["decoded_memo"] = tx["decoded_memo"]
    except KeyError:
        pass

    return dict(
        signedTransaction=signedTransaction
    )


def create_address():
    """
        Simply reads the private key from the config and creates a new random customer_id
    """
    if Config.get("bitshares", "keep_keys_private", True):
        return {
            "privateKey": "keep_keys_private",
            "publicAddress": create_unique_address(Config.get_config()["bitshares"]["exchange_account_id"])
        }
    else:
        return {
            "privateKey": Config.get("bitshares", "exchange_account_active_key"),
            "publicAddress": create_unique_address(Config.get("bitshares", "exchange_account_id")),
            "addressContext": Config.get("bitshares", "exchange_account_memo_key"),
        }
