import datetime
import strict_rfc3339
from . import Config


def date_to_string(date_object=None):
    """ creates a rfc3339 conform string represenation of a date,
        can also be given as str YYYY-mm-dd HH:MM:SS, assuming local
        machine timezone

        :param date_object: the date to be converted
        :type date_object: date object or str
    """
    if type(date_object) == int:
        date_object = datetime.datetime.fromtimestamp(date_object)
    if type(date_object) == float:
        date_object = datetime.datetime.fromtimestamp(date_object)
    if type(date_object) == str:
        date_object = datetime.datetime.strptime(date_object + "+0000",
                                                 '%Y-%m-%d %H:%M:%S%z')
    if not date_object:
        return strict_rfc3339.now_to_rfc3339_utcoffset()
    else:
        return strict_rfc3339.timestamp_to_rfc3339_utcoffset(
            date_object.timestamp())


def string_to_date(date_string):
    """ converts the given string to a date object

        :param date_string: rfc3339 conform string
        :type date_string: str
    """
    if type(date_string) == str:
        return datetime.datetime.fromtimestamp(
            strict_rfc3339.rfc3339_to_timestamp(date_string))
    raise Exception("Only string covnersion supported")


def is_exchange_account(account_id_or_name):
    """ checks if the given account id is configured as the exchange account

        :param account_id_or_name: format 1.2.XXX or name
        :type account_id: str
    """
    # add different ids if necessary at some point
    return account_id_or_name == get_exchange_account_id() or\
        account_id_or_name == get_exchange_account_id()


def get_exchange_account_name():
    """ gets the exchange account name that is configured in config.yaml
    """
    return Config.get_config()["bitshares"]["exchange_account_name"]


def get_exchange_account_id():
    """ gets the exchange account id that is configured in config.yaml
    """
    return Config.get_config()["bitshares"]["exchange_account_id"]


def get_exchange_active_key():
    """ gets the exchange accounts active private key that is configured in config.yaml
    """
    return Config.get_config()["bitshares"]["exchange_account_active_key"]


def get_exchange_memo_key():
    """ gets the exchange accounts active private key that is configured in config.yaml
    """
    return Config.get_config()["bitshares"]["exchange_account_memo_key"]
