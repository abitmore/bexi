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


def get_from_address_from_operation(operation):
    """ returns the from address of the given operation.
        if the from address is the exchange account,
        the address contains the customer_id, otherwise empty string
        is set

        :param operation: operation formatted for operation storage
        :type operation: dict
    """
    if utils.is_exchange_account(operation["from"]):
        return get_address_from_operation(operation)
    else:
        return ensure_account_name(operation["from"])


def get_to_address_from_operation(operation):
    """ returns the to address of the given operation.
        if the to address is the exchange account,
        the address contains the customer_id, otherwise empty string
        is set

        :param operation: operation formatted for operation storage
        :type operation: dict
    """
    if utils.is_exchange_account(operation["to"]) and not utils.is_exchange_account(operation["from"]):
        return get_address_from_operation(operation)
    else:
        return ensure_account_name(operation["to"])


def get_address_from_operation(operation):
    """ assumes that the operation is either from or to an exchange account.
        the address of this operation is then returned as
        <exchange_account_id>DELIMITER<customer_id>

        :param operation: operation formatted for operation storage
        :type operation: dict
    """
    if utils.is_exchange_account(operation["from"]) and utils.is_exchange_account(operation["to"]):
        return ensure_account_name(operation["from"]) + DELIMITER + operation["customer_id"]
    elif utils.is_exchange_account(operation["from"]):
        return ensure_account_name(operation["from"]) + DELIMITER + operation["customer_id"]
    elif utils.is_exchange_account(operation["to"]):
        return ensure_account_name(operation["to"]) + DELIMITER + operation["customer_id"]
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


def create_memo(address, incident_id):
    """ Create plain text memo for an address/incident pair.
        The memo will contain <customer_id>DELIMITER<incident_id>,
        this is done to have full transparency on the blockchain

        :param address: address in the format <account_id>DELIMITER<customer_id>
        :type address: str
        :param incident_id: unique incident id
        :type incident_id: str
    """
    address = split_unique_address(address)

    memo = ""

    if address["customer_id"]:
        memo = memo + address["customer_id"]
    if incident_id:
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
