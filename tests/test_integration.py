from flask.helpers import url_for
import json

from tests.abstract_tests import AFlaskTest

from bexi import Config, factory
from bexi.addresses import split_unique_address, create_unique_address
from bexi.connection import requires_blockchain
from bexi.operation_storage.operation_formatter import decode_operation


class TestIntegration(AFlaskTest):

    def setUp(self):
        super(TestIntegration, self).setUp()

        # allow broadcasting in this test!
        Config.data["bitshares"]["connection"]["Test"]["nobroadcast"] = False

    def test_is_alive(self):
        response = self.client.get(url_for('Common.isalive'))

        assert response.json ==\
            {'env': None, 'isDebug': False, 'name': 'bexi', 'version': Config.get_config()["wsgi"]["version"]}

        # isDebug is false because the flask server is not started with debug=True

    def test_wallet(self):
        response = self.client.post(url_for('Blockchain.SignService.wallets'))

        response = response.json

        self.assertEqual(response["privateKey"], Config.get_config()["bitshares"]["exchange_account_active_key"])

        addrs = split_unique_address(response["publicAddress"])

        self.assertEqual(addrs["account_id"], Config.get_config()["bitshares"]["exchange_account_id"])

        self.assertEqual(len(addrs["customer_id"]), 36)

    @requires_blockchain
    def test_track_balance(self):
        addressDW = self.client.post(url_for('Blockchain.SignService.wallets')).json["publicAddress"]
        addressEW = create_unique_address(self.get_customer_id(), "")

        build_transaction = {
            "operationId": "abc",
            "fromAddress": addressEW,
            "toAddress": addressDW,
            "assetId": "1.3.0",
            "amount": 100000,
            "includeFee": False
        }

        response = self.client.get(url_for('Blockchain.Api.address_validity', address=addressDW))
        assert response.status_code == 200

        response = self.client.post(url_for('Blockchain.Api.observe_address', address=addressDW))
        assert response.status_code == 200

        transaction = self.client.post(url_for('Blockchain.Api.build_transaction'),
                                       data=json.dumps(build_transaction))

        sign_transaction = {
            "transactionContext": transaction.json["transactionContext"],
            "privateKeys": [self.get_customer_active_key()]
        }
        sign_transaction["transactionContext"]["prefix"] = "TEST"
        signed_transaction = self.client.post(url_for('Blockchain.SignService.sign'),
                                              data=json.dumps(sign_transaction))

        broadcast_transaction = {
            "operationId": build_transaction["operationId"],
            "signedTransaction": signed_transaction.json["signedTransaction"]
        }

        broadcast = self.client.post(url_for('Blockchain.Api.broadcast_transaction'),
                                     data=json.dumps(broadcast_transaction))
        assert broadcast.status_code == 200

        tx = signed_transaction.json["signedTransaction"]
        for operation in tx["operations"]:
            j = dict(
                op=operation,
                decoded_memo=tx["decoded_memo"],
                expiration=tx["expiration"],
                block_num=12124,
                op_in_tx=0,
                transaction_id=tx["transaction_id"]
            )
            factory.get_operation_storage(purge=False).flag_operation_completed(decode_operation(j))

        response = self.client.post(url_for('Blockchain.Api.get_balances') + "?take=1")
        assert response.status_code == 200

        self.assertEqual(response.json["items"][0]["balance"], 100000)

