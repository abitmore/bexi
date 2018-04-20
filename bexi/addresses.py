import uuid
from . import utils
from .connection import requires_blockchain
from bitshares.account import Account


DELIMITER = ":"


def split_unique_address(address):
    """
    Splits the address into bitshares account id and customer id

    :param address: address in the format <account_id>DELIMITER<customer_id>
    :type address: str
    """
    splitted = address.split(DELIMITER)
    always = {"account_id": ensure_account_id(splitted[0])}
    if len(splitted) == 2:
        always["customer_id"] = splitted[1]
    else:
        always["customer_id"] = ""
    if len(splitted) == 3:
        always["incident_id"] = splitted[2]
    return always


def get_from_address(operation):
    """ returns the from address of the given operation.
        if the from address is the exchange account,
        the address contains the customer_id, otherwise empty string
        is set

        :param operation: operation formatted for operation storage
        :type operation: dict
    """
    if _is_internal(operation["from"], operation["to"]):
        # internal transfer
        return create_unique_address(operation["from"], operation["customer_id"])
    else:
        return create_unique_address(operation["from"], "")


def get_to_address(operation):
    """ returns the to address of the given operation.
        if the to address is the exchange account,
        the address contains the customer_id, otherwise empty string
        is set

        :param operation: operation formatted for operation storage
        :type operation: dict
    """
    if not _is_internal(operation["from"], operation["to"]):
        # no internal transfer
        return create_unique_address(operation["to"], operation["customer_id"])
    else:
        return create_unique_address(operation["to"], "")


def get_tracking_address(operation):
    """
        Get the tracking address of this operation, either from or to an exchange account.
        Decision depends on internal transfer, deposit, withdraw operation

        :param operation: operation formatted for operation storage
        :type operation: dict

        :returns address as defined in `func`:create_unique_address
    """
    if _is_internal(operation["from"], operation["to"]):
        # internal transfer
        return create_unique_address(operation["from"], operation["customer_id"])
    elif _is_withdraw(operation["from"], operation["to"]):
        # withdraw
        return create_unique_address(operation["to"], operation["customer_id"])
    elif _is_deposit(operation["from"], operation["to"]):
        # deposit
        return create_unique_address(operation["to"], operation["customer_id"])
    raise Exception("No operaton concerning this exchange")


def decide_tracking_address(from_address, to_address):
    """
        Given two addresses it decides which is the tracking address for the underlying operation.
        Creates and splits the address to use common functionality buried in both methods.
        Decision depends on internal transfer, deposit, withdraw operation

        :param from_address: from address
        :type from_address: str or split address
        :param to_address: to address
        :type to_address: str or split address3

        :returns split address as defined in `func`:split_unique_address
    """
    if type(from_address) == str:
        from_address = split_unique_address(from_address)
    if type(to_address) == str:
        to_address = split_unique_address(to_address)
    if _is_internal(from_address, to_address):
        # internal transfer
        return split_unique_address(create_unique_address(from_address["account_id"], from_address["customer_id"]))
    elif _is_withdraw(from_address, to_address):
        # withdraw
        return split_unique_address(create_unique_address(to_address["account_id"], to_address["customer_id"]))
    elif _is_deposit(from_address, to_address):
        # deposit
        return split_unique_address(create_unique_address(to_address["account_id"], to_address["customer_id"]))
    raise Exception("No operaton concerning this exchange")


@requires_blockchain
def _account_name_to_id(account_name, bitshares_instance):
    return Account(account_name, bitshares_instance=bitshares_instance)["id"]


@requires_blockchain
def _account_id_to_name(account_id, bitshares_instance):
    return Account(account_id, bitshares_instance=bitshares_instance)["name"]


def ensure_account_name(account_id_or_name):
    if account_id_or_name.startswith("1.2."):
        if account_id_or_name == utils.get_exchange_account_id():
            return utils.get_exchange_account_name()
        else:
            return _account_id_to_name(account_id_or_name)
    return account_id_or_name


def ensure_account_id(account_id_or_name):
    if not account_id_or_name.startswith("1.2."):
        if account_id_or_name == utils.get_exchange_account_name():
            return utils.get_exchange_account_id()
        else:
            return _account_name_to_id(account_id_or_name)
    return account_id_or_name


def create_unique_address(account_id_or_name, randomizer=uuid.uuid4):
    """
    The external exchange requires a unique address, which is constructed using
    the bitshares account_id and some unique random string used as the customer_id.
    Account id gets resolved into an account name.

    Format: <account_name>DELIMITER<customer_id>

    :param account_id_or_name: bitshares account id or name
    :type account_id_or_name: string, format 1.2.XXX for ids
    :param randomizer: random string generator
    :type randomizer: function handle
    """
    account_id_or_name = ensure_account_name(account_id_or_name)
    if type(randomizer) == str:
        if randomizer == "":
            return account_id_or_name
        else:
            return account_id_or_name + DELIMITER + randomizer
    return account_id_or_name + DELIMITER + str(randomizer())


def _is_withdraw(from_address, to_address):
    if type(from_address) == dict:
        from_address = from_address["account_id"]
    if type(to_address) == dict:
        to_address = to_address["account_id"]
    return utils.is_exchange_account(from_address) and not utils.is_exchange_account(to_address)


def _is_deposit(from_address, to_address):
    if type(from_address) == dict:
        from_address = from_address["account_id"]
    if type(to_address) == dict:
        to_address = to_address["account_id"]
    return not utils.is_exchange_account(from_address) and utils.is_exchange_account(to_address)


def _is_internal(from_address, to_address):
    if type(from_address) == dict:
        from_address = from_address["account_id"]
    if type(to_address) == dict:
        to_address = to_address["account_id"]
    return utils.is_exchange_account(from_address) and utils.is_exchange_account(to_address)


def create_memo(from_address, to_address, incident_id):
    """ Create plain text memo for a transfer as defined by arguments.
        Depending on the case (internal transfer, deposit, withdraw operation),
        the memo will contain [<customer_id>[DELIMITER<incident_id>]].

        :param address: address in the format <account_id>DELIMITER<customer_id>
        :type address: str
        :param incident_id: unique incident id
        :type incident_id: str
    """
    address = decide_tracking_address(from_address, to_address)

    memo = ""

    if address["customer_id"]:
        memo = memo + address["customer_id"]
    if incident_id and not _is_withdraw(from_address, to_address):
        if memo != "":
            memo = memo + DELIMITER + incident_id
        else:
            memo = " " + DELIMITER + incident_id
    return memo


def split_memo(memo):
    """ Split plain text memo into address/incident pair

        :param memo: memo string in the format <customer_id>DELIMITER<incident_id>,
                     incident_id is optional
        :type memo: str
    """
    if not memo or memo == "":
        raise ValueError()

    splitted = memo.split(DELIMITER)
    always = {"customer_id": splitted[0]}
    if len(splitted) == 2:
        always["incident_id"] = splitted[1]
    else:
        always["incident_id"] = None
    return always
