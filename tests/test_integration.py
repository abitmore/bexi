from flask.helpers import url_for
import json

from tests.abstract_tests import AFlaskTest

from bexi import Config, factory
from bexi.addresses import split_unique_address, create_unique_address
from bexi.connection import requires_blockchain
from bexi.operation_storage.operation_formatter import decode_operation


class TestIntegration(AFlaskTest):

    def test_is_alive(self):
        response = self.client.get(url_for('Common.isalive'))

        assert response.json ==\
            {'env': None, 'isDebug': False, 'name': 'bexi', 'version': '0.0.1'}

        # isDebug is false because the flask server is not started with debug=True

    def test_wallet(self):
        response = self.client.post(url_for('Blockchain.SignService.wallets'))

        response = response.json

        self.assertEqual(response["privateKey"], "5KD3ZFrxVFJReHHcss8b2KkoccBJCTQCZy6HLfZ3TY5dkoAD27N")

        addrs = split_unique_address(response["publicAddress"])

        self.assertEqual(addrs["account_id"], Config.get_config()["bitshares"]["exchange_account_id"])

        self.assertEqual(len(addrs["customer_id"]), 36)

    @requires_blockchain
    def test_track_balance(self):
        keys = {"lykke-test": {"memo": "5KD3ZFrxVFJReHHcss8b2KkoccBJCTQCZy6HLfZ3TY5dkoAD27N",
                               "active": "5KD3ZFrxVFJReHHcss8b2KkoccBJCTQCZy6HLfZ3TY5dkoAD27N",
                               "id": "1.2.20137"},
                "lykke-customer": {"memo": "5HuuC1pbw5fsJFbTvR9VXbnv1qp9KSb3LpwUrhRLsUVgukGFu1G",
                                   "active": "5HuuC1pbw5fsJFbTvR9VXbnv1qp9KSb3LpwUrhRLsUVgukGFu1G",
                                   "id": "1.2.20138"}}

        addressDW = self.client.post(url_for('Blockchain.SignService.wallets')).json["publicAddress"]
        addressEW = create_unique_address("1.2.20138", "")

        build_transaction = {
            "operationId": "abc",
            "fromAddress": addressEW,
            "toAddress": addressDW,
            "assetId": "1.3.0",
            "amount": 1000,
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
            "privateKeys": ["5KjRsxwNsoJ8PjCjM4p8Jja3krUQ8uFjw7rRf3v7DH8kRZNhNW1"]
        }
        sign_transaction["transactionContext"]["operations"][0][1].update({"prefix": "TEST"})
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

        self.assertEqual(response.json["items"][0]["balance"], 1000)

