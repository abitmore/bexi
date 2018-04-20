from pymongo import MongoClient
import logging
import pprint

from . import Config
from .operation_storage.mongodb_storage import MongoDBOperationsStorage
from .operation_storage.azure_storage import AzureOperationsStorage


def get_operation_storage(use=None, purge=None):
    """ This factory initializes an IOperationStorage object specified by use.
        If necessary, the database is purged before use.

        :param use: Indicates which implementation of IOperationStorage will be used
                    Available:
                        azure
                        azuretest
                        mongodb
                        mongodbtest
                    Default: as configured in config.yaml
        :type use: String
        :param purge: Indicates if the database should be purged
        :type purge: boolean, for default behavior set to None.
                     no purge for real connections,
                     purge for test connections
    """

    printConfig = False
    if not use:
        # default operation storage is wanted, print config for clarification
        printConfig = True
        use = Config.get("operation_storage", "use")

    def get_mongodb(use_config):
        return MongoDBOperationsStorage(mongodb_config=use_config)

    def get_mongodb_test(use_config):
        # set short timeouts to speed up testing
        mongodb_client = MongoClient(host=use_config["seeds"],
                                     socketTimeoutMS=500,
                                     connectTimeoutMS=500,
                                     serverSelectionTimeoutMS=1500
                                     )
        return MongoDBOperationsStorage(mongodb_config=use_config, mongodb_client=mongodb_client, purge=True)

    def get_azure(use_config):
        return AzureOperationsStorage(azure_config=use_config)

    def get_azure_test(use_config):
        if purge is None:
            return AzureOperationsStorage(azure_config=use_config, purge=True)
        else:
            return AzureOperationsStorage(azure_config=use_config, purge=purge)

    config = Config.get("operation_storage")
    use_config = config[use]

    use_choice = {
        "mongodb": lambda: get_mongodb(use_config),
        "mongodbtest": lambda: get_mongodb_test(use_config),
        "azure": lambda: get_azure(use_config),
        "azuretest": lambda: get_azure_test(use_config)
    }

    if printConfig:
        logging.getLogger(__name__).debug("Operation storage initialized with use=" + use)

    return use_choice[use]()
