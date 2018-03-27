from tests.abstract_tests import ATestOperationStorage

from bexi import utils

from bexi.wsgi.manage_service.implementations import MemoMatchingFailedException
from bexi.addresses import get_address_from_operation, create_unique_address, DELIMITER
from bexi.wsgi.manage_service.views import implementations
from bexi.wsgi.manage_service.implementations import AssetNotFoundException
from bexi.operation_storage.interface import AddressAlreadyTrackedException,\
    AddressNotTrackedException, OperationNotFoundException
from bexi.wsgi import manage_service
from bexi.wsgi import sign_service

from flask import json
from bitshares.exceptions import AccountDoesNotExistsException


class TestBlockchainApi(ATestOperationStorage):

    def setUp(self):
        super(TestBlockchainApi, self).setUp()
        implementations._get_os(storage=self.storage)

    def test_get_all_assets(self):
        assert implementations.get_all_assets(0, 0) ==\
            {'continuation': 0, 'items': []}

        assert implementations.get_all_assets(1, 0) ==\
            {'continuation': 1, 'items': [{'assetId': '1.3.0', 'address': 'None', 'name': 'BTS', 'accuracy': 5}]}

        assert implementations.get_all_assets(1, 1) ==\
            {'continuation': 2, 'items': [{'assetId': '1.3.121', 'address': 'None', 'name': 'USD', 'accuracy': 4}]}

        assert implementations.get_all_assets(5, 0) ==\
            {'continuation': None, 'items': [{'assetId': '1.3.0', 'address': 'None', 'name': 'BTS', 'accuracy': 5}, {'assetId': '1.3.121', 'address': 'None', 'name': 'USD', 'accuracy': 4}, {'assetId': '1.3.120', 'address': 'None', 'name': 'EUR', 'accuracy': 4}]}

        implementations.get_all_assets(0, 0)

    def test_get_asset(self):
        assert implementations.get_asset('1.3.0') ==\
            {'assetId': '1.3.0', 'address': 'None', 'name': 'BTS', 'accuracy': 5}

        self.assertRaises(
            AssetNotFoundException,
            implementations.get_asset,
            '1.3.1')

    def test_validate_address(self):
        assert implementations.validate_address(create_unique_address('xeroc')) ==\
            {'isValid': True}

        assert implementations.validate_address(create_unique_address('this_account_will_never_exist')) ==\
            {'isValid': False}

        assert implementations.validate_address(create_unique_address('!@$%25^&*(')) ==\
            {'isValid': False}

    def test_observe_address(self):
        address = create_unique_address("some_id", "user_name_bla")

        self.assertRaises(
            AccountDoesNotExistsException,
            implementations.observe_address,
            address)

        address = create_unique_address(utils.get_exchange_account_id(), "user_name_bla")

        implementations.observe_address(address)

        self.assertRaises(
            AddressAlreadyTrackedException,
            implementations.observe_address,
            address)

        implementations.unobserve_address(address)
        self.assertRaises(
            AddressNotTrackedException,
            implementations.unobserve_address,
            address)

    def test_get_balances(self):
        assert implementations.get_balances(1, 0) ==\
            {'continuation': None, 'items': []}

        transfer = self.get_completed_op()
        transfer["amount_asset_id"] = "1.3.0"

        transfer["customer_id"] = "user_name_bla"
        transfer["to"] = utils.get_exchange_account_id()
        implementations._get_os().insert_operation(transfer)

        first = transfer.copy()

        transfer["customer_id"] = "user_name_bla_2"
        transfer["chain_identifier"] = "24:25"
        implementations._get_os().insert_operation(transfer)

        transfer["customer_id"] = "user_name_bla_2"
        transfer["chain_identifier"] = "24:26"
        transfer["from"] = utils.get_exchange_account_id()
        transfer["to"] = "some_dude"
        implementations._get_os().insert_operation(transfer)

        implementations.observe_address(get_address_from_operation(first))
        implementations.observe_address(get_address_from_operation(transfer))

        implementations._get_os().set_last_head_block_num(1010)

        assert implementations.get_balances(1, 0) ==\
            {'continuation': None, 'items': [{'address': get_address_from_operation(first), 'assetId': '1.3.0', 'balance': 50000000, 'block': 1010}]}

    def test_build_transaction_not_enough_balance(self):
        from_id = utils.get_exchange_account_id()
        from_memo_key = utils.get_exchange_memo_key()
        tx = implementations.build_transaction(
            "Foobar",
            from_id + DELIMITER + "from_customer_id",
            from_memo_key,
            self.get_customer_id() + DELIMITER + "to_customer_id",
            "1.3.0",
            10000,
            False
        )

        tx = json.loads(tx["transactionContext"])

        self.assertEqual(
            len(tx["operations"]),
            1
        )
        self.assertEqual(
            tx["operations"][0][0],
            0  # transfer
        )
        op = tx["operations"][0][1]
        self.assertEqual(
            op["from"],
            from_id,  # lykkee account id
            "1.2.397770",  # blockchainbv account
        )

        self.assertEqual(
            op["amount"]["asset_id"],
            "1.3.0")

        self.assertEqual(
            op["amount"]["amount"],
            10000)

        self.assertGreater(
            op["fee"]["amount"],
            0)

    def test_build_transaction(self):
        from_id = utils.get_exchange_account_id()
        from_memo_key = utils.get_exchange_memo_key()
        tx = implementations.build_transaction(
            "Foobar",
            from_id + DELIMITER + "from_customer_id",
            from_memo_key,
            self.get_customer_id() + DELIMITER + "to_customer_id",
            "1.3.0",
            10000,
            False
        )

        tx = json.loads(tx["transactionContext"])

        self.assertEqual(
            len(tx["operations"]),
            1
        )
        self.assertEqual(
            tx["operations"][0][0],
            0  # transfer
        )
        op = tx["operations"][0][1]
        self.assertEqual(
            op["from"],
            from_id,  # lykkee account id
            "1.2.397770",  # blockchainbv account
        )

        self.assertEqual(
            op["amount"]["asset_id"],
            "1.3.0")

        self.assertEqual(
            op["amount"]["amount"],
            10000)

        self.assertGreater(
            op["fee"]["amount"],
            0)

    def test_build_transaction_wrong_memo(self):
        from_id = "1.2.20139"
        from_memo_key = utils.get_exchange_memo_key()

        self.assertRaises(MemoMatchingFailedException,
                          implementations.build_transaction,
                          "Foobar",
                          from_id + DELIMITER + "from_customer_id",
                          None,
                          utils.get_exchange_account_id() + DELIMITER + "to_customer_id",
                          "1.3.0",
                          10000,
                          False)

        self.assertRaises(MemoMatchingFailedException,
                          implementations.build_transaction,
                          "Foobar",
                          from_id + DELIMITER + "from_customer_id",
                          from_memo_key,
                          utils.get_exchange_account_id() + DELIMITER + "to_customer_id",
                          "1.3.0",
                          10000,
                          False)

    def test_build_transaction2(self):
        from_id = utils.get_exchange_account_id()
        from_memo_key = utils.get_exchange_memo_key()
        tx = implementations.build_transaction(
            "Foobar",
            from_id + DELIMITER + "from_customer_id",
            from_memo_key,
            self.get_customer_id() + DELIMITER + "to_customer_id",
            "1.3.0",
            10000,
            True       # This changes behavior!!!!!!!!!!!!!!!
        )
        tx = json.loads(tx["transactionContext"])
        op = tx["operations"][0][1]
        self.assertLess(
            op["amount"]["amount"],
            10000)

        self.assertGreater(
            op["fee"]["amount"],
            0)

    def test_broadcast_transaction(self):
        from_id = utils.get_exchange_account_id()
        from_memo_key = utils.get_exchange_memo_key()
        tx = manage_service.implementations.build_transaction(
            "Foobar",
            from_id + DELIMITER + "from_customer_id",
            from_memo_key,
            self.get_customer_id() + DELIMITER + "to_customer_id",
            "1.3.0",
            100000,
            False
        )

        stx = sign_service.implementations.sign(
            tx["transactionContext"],
            [utils.get_exchange_active_key()]
        )

        implementations.broadcast_transaction(
            stx["signedTransaction"]
        )

    def test_get_and_delete_broadcasted(self):
        completed = self.get_completed_op()
        completed["incident_id"] = "some_incident"
        implementations._get_os().insert_operation(completed)

        operation = implementations.get_broadcasted_transaction("some_incident")

        assert operation.get("block", None) is not None

        implementations.delete_broadcasted_transaction("some_incident")

        self.assertRaises(
            OperationNotFoundException,
            implementations.get_broadcasted_transaction,
            "some_incident")

        in_progress = self.get_in_progress_op()
        in_progress["incident_id"] = "some_incident"
        implementations._get_os().insert_operation(in_progress)
        implementations._get_os().flag_operation_failed(in_progress, message="manual fail")

        operation = implementations.get_broadcasted_transaction("some_incident")

        assert operation.get("block", None) is None

    def test_get_address_history_to(self):
        transfer = self.get_completed_op()
        transfer["incident_id"] = "incident_id_1234"
        transfer["chain_identifier"] = "chainidentifier_1234"
        transfer["customer_id"] = "user_name_bla"
        transfer["to"] = utils.get_exchange_account_id()
        implementations._get_os().insert_operation(transfer)

        history = implementations.get_address_history_to(get_address_from_operation(transfer), 1, 0)

        self.assertEqual(
            history,
            [{'operationId': 'incident_id_1234', 'timestamp': history[0]['timestamp'], 'fromAddress': '1.2.114406:::', 'toAddress': '1.2.20137:::user_name_bla', 'assetId': '1.3.121', 'amount': '50000000', 'hash': 'chainidentifier_1234'}]
        )

    def test_get_address_history_from(self):
        transfer = self.get_completed_op()
        transfer["incident_id"] = "incident_id_1235"
        transfer["chain_identifier"] = "chainidentifier_1235"
        transfer["customer_id"] = "user_name_bla"
        transfer["from"] = utils.get_exchange_account_id()
        implementations._get_os().insert_operation(transfer)

        history = implementations.get_address_history_from(get_address_from_operation(transfer), 1, 0)

        self.assertEqual(
            history,
            [{'operationId': 'incident_id_1235', 'timestamp': history[0]['timestamp'], 'fromAddress': '1.2.20137:::user_name_bla', 'toAddress': '1.2.381086:::', 'assetId': '1.3.121', 'amount': '50000000', 'hash': 'chainidentifier_1235'}]
        )
