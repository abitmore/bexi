from flask.helpers import url_for
import json

from tests.abstract_tests import AFlaskTest

from bexi import Config, factory, utils
from bexi.addresses import split_unique_address, create_unique_address
from bexi.connection import requires_blockchain
from bexi.blockchain_monitor import BlockchainMonitor
from bitshares.bitshares import BitShares


class TestIntegration(AFlaskTest):

    def setUp(self):
        super(TestIntegration, self).setUp()

        # allow broadcasting in this test!
        Config.data["bitshares"]["connection"]["Test"]["nobroadcast"] = False

    def test_is_alive(self):
        response = self.client.get(url_for('Common.isalive'))

        assert response.json ==\
            {'env': None, 'isDebug': False, 'name': 'bexi', 'version': Config.get("wsgi", "version")}

        # isDebug is false because the flask server is not started with debug=True

    def test_wallet(self):
        response = self.client.post(url_for('Blockchain.SignService.wallets'))

        response = response.json

        if Config.get("bitshares", "keep_keys_private", True):
            self.assertEqual(response["privateKey"], "keep_keys_private")
        else:
            self.assertEqual(response["privateKey"], Config.get("bitshares", "exchange_account_active_key"))

        addrs = split_unique_address(response["publicAddress"])

        self.assertEqual(addrs["account_id"], Config.get("bitshares", "exchange_account_id"))

        self.assertEqual(len(addrs["customer_id"]), 36)

    @requires_blockchain
    def test_track_balance(self, bitshares_instance=None):
        addressDW = self.client.post(url_for('Blockchain.SignService.wallets')).json["publicAddress"]

        addressEW = create_unique_address(self.get_customer_id(), "")

        addressHW = self.client.post(url_for('Blockchain.SignService.wallets')).json["publicAddress"]

        customer_id = split_unique_address(addressDW)["customer_id"]

        response = self.client.get(url_for('Blockchain.Api.address_validity', address=addressDW))
        assert response.status_code == 200

        response = self.client.post(url_for('Blockchain.Api.observe_address', address=addressDW))
        assert response.status_code == 200

        response = self.client.post(url_for('Blockchain.Api.observe_address', address=addressHW))
        assert response.status_code == 200

        def build_sign_and_broadcast(op, memo_key, active_key):
            op["fromAddressContext"] = memo_key
            transaction = self.client.post(url_for('Blockchain.Api.build_transaction'),
                                           data=json.dumps(op))

            assert transaction.status_code == 200

            sign_transaction = {
                "transactionContext": transaction.json["transactionContext"],
                "privateKeys": [active_key]
            }
            signed_transaction = self.client.post(url_for('Blockchain.SignService.sign'),
                                                  data=json.dumps(sign_transaction))
            broadcast_transaction = {
                "operationId": op["operationId"],
                "signedTransaction": signed_transaction.json["signedTransaction"]
            }
            broadcast = self.client.post(url_for('Blockchain.Api.broadcast_transaction'),
                                         data=json.dumps(broadcast_transaction))
            assert broadcast.status_code == 200

            return broadcast.json["block_num"]

        def flag_completed(block_num, key):
            network = Config.get("network_type")
            connection = Config.get("bitshares", "connection", network)
            connection["keys"] = key
            instance = BitShares(**connection)

            store = factory.get_operation_storage(purge=False)
            irr = instance.rpc.get_dynamic_global_properties().get("last_irreversible_block_num")
            head = instance.rpc.get_dynamic_global_properties().get("head_block_number")

            print("Blockchain Monitor: Looking for block " + str(block_num), ", current head=" + str(head) + ", irreversible=" + str(irr))

            monitor = BlockchainMonitor(
                storage=store,
                bitshares_instance=instance)
            monitor.start_block = block_num - 1
            monitor.stop_block = block_num + 1
            monitor.listen()

        block_num = build_sign_and_broadcast(
            {
                "operationId": "deposit",
                "fromAddress": addressEW,
                "toAddress": addressDW,
                "assetId": "1.3.0",
                "amount": 110000,
                "includeFee": False
            },
            self.get_customer_memo_key(),
            self.get_customer_active_key()
        )
        flag_completed(block_num, utils.get_exchange_memo_key())

        response = self.client.post(url_for('Blockchain.Api.get_balances') + "?take=1")
        assert response.status_code == 200
        self.assertEqual(response.json["items"][0]["balance"], 110000)

        block_num = build_sign_and_broadcast(
            {
                "operationId": "DWtoHW",
                "fromAddress": addressDW,
                "toAddress": addressHW,
                "assetId": "1.3.0",
                "amount": 100000,
                "includeFee": False
            },
            utils.get_exchange_memo_key(),
            utils.get_exchange_active_key()
        )

        block_num = build_sign_and_broadcast(
            {
                "operationId": "withrawal",
                "fromAddress": addressHW,
                "toAddress": create_unique_address(self.get_customer_id(), customer_id),
                "assetId": "1.3.0",
                "amount": 100000,
                "includeFee": False
            },
            utils.get_exchange_memo_key(),
            utils.get_exchange_active_key()
        )
        flag_completed(block_num, self.get_customer_memo_key())

        response = self.client.post(url_for('Blockchain.Api.get_balances') + "?take=1")
        assert response.status_code == 200

        self.assertEqual(response.json["items"][0]["balance"], 10000)
