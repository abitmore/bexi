import unittest
from flask_testing import TestCase

from bexi.addresses import create_unique_address
from bexi.wsgi.app import create_sign_service_app,\
    create_manage_service_app, create_common_app
from bexi import Config
from bexi.operation_storage.operation_formatter import decode_operation
from bexi.factory import get_operation_storage
from bexi import connection


class ATestnetTest(unittest.TestCase):

    def setUp(self):
        if Config.data:
            connection.reset()

        Config.load()
        Config.load("../tests/config_test.yaml")
        Config.data["operation_storage"]["use"] = "azuretest"
        Config.data["network_type"] = "Test"
        Config.data["bitshares"]["connection"]["Test"]["nobroadcast"] = True

    def tearDown(self):
        Config.reset()

    def get_customer_active_key(self):
        """ reads the test account configuration from config_test.yaml
        """
        return Config.get_config()["bitshares"]["customer_account_active_key"]

    def get_customer_id(self):
        """ reads the test account configuration from config_test.yaml
        """
        return Config.get_config()["bitshares"]["customer_account_id"]


class AFlaskTest(TestCase):

    def create_app(self):
        self.setUp()

        app = create_manage_service_app(
            create_sign_service_app(
                create_common_app()))

        return app

    def setUp(self):
        if Config.data:
            connection.reset()

        Config.load()
        Config.load("../tests/config_test.yaml")
        Config.data["operation_storage"]["use"] = "azuretest"
        Config.data["network_type"] = "Test"
        Config.data["bitshares"]["connection"]["Test"]["nobroadcast"] = True

    def tearDown(self):
        Config.reset()

    def get_customer_active_key(self):
        """ reads the test account configuration from config_test.yaml
        """
        return Config.get_config()["bitshares"]["customer_account_active_key"]

    def get_customer_id(self):
        """ reads the test account configuration from config_test.yaml
        """
        return Config.get_config()["bitshares"]["customer_account_id"]

    def get_customer_memo_key(self):
        """ reads the test account configuration from config_test.yaml
        """
        return Config.get_config()["bitshares"]["customer_account_memo_key"]


class ATestOperationStorage(ATestnetTest):

    TEST_OP = {'block_num': 23645414,
               'transaction_id': 23,
               "op_in_tx": 2,
               'op': ['transfer',
                      {
                          "fee": {
                              "amount": 1759,
                              "asset_id": "1.3.0"
                          },
                          "from": "1.2.20407",
                          "to": "1.2.20477",
                          "amount": {
                              "amount": 50000000,
                              "asset_id": "1.3.121"
                          },
                          "memo": {
                              "from": "BTS6A9Qsp2FrrCWNndZmWqbeLq6g7Lr1T8Y9sQ5RbqutoeW5nBTAU",
                              "to": "BTS5HDNjR25RHQAJ2Esnt6Yz1tgyr4fdwJEXv5r8wx5ynLSkDsyMQ",
                              "nonce": "9243173171060559811",
                              "message": "98af198ef4d58fc7608dee97c970dd2d684ce7ab03617123f702c156659f5eb2"
                          },
                          "extensions": []
                      }],
               "decoded_memo": create_unique_address("some_customer_id", "some_operation_id"),
               'expiration': "2018-01-12T08:25:29"
               }

    def get_in_progress_op(self):
        in_progress_op = decode_operation(self.TEST_OP.copy())

        in_progress_op.pop("block_num")

        return in_progress_op

    def get_completed_op(self):
        return decode_operation(self.TEST_OP.copy())

    def __init__(self, *args, **kwargs):
        super(ATestOperationStorage, self).__init__(*args, **kwargs)

    def setUp(self):
        super(ATestOperationStorage, self).setUp()

        self.storage = get_operation_storage("mongodbtest")


