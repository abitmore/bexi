from flask.helpers import url_for
import json

from tests.abstract_tests import AFlaskTest

from bexi import Config, factory, utils
from bexi.addresses import split_unique_address, create_unique_address
from bexi.connection import requires_blockchain
from bexi.blockchain_monitor import BlockchainMonitor
from bitshares.bitshares import BitShares
from bexi import __VERSION__


class TestIntegration(AFlaskTest):

    def setUp(self):
        super(TestIntegration, self).setUp()

        # allow broadcasting in this test!
        Config.data["bitshares"]["connection"]["Test"]["nobroadcast"] = False

    def test_is_alive(self):
        response = self.client.get(url_for('Common.isalive'))

        self.assertEqual(response.json,
                         {'env': None, 'isDebug': False, 'name': 'bexi', 'version': __VERSION__, 'contractVersion': '1.1.3'})

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

#         customer_id = split_unique_address(addressDW)["customer_id"]

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

            print(broadcast_transaction)

            return broadcast.json["block_num"]

        def flag_completed(block_num):
            network = Config.get("network_type")
            connection = Config.get("bitshares", "connection", network)
#             connection["keys"] = key
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
                "operationId": "cbeea30e-2218-4405-9089-86d003e4df60",
                "fromAddress": addressEW,
                "toAddress": addressDW,
                "assetId": "1.3.0",
                "amount": 110000,
                "includeFee": False
            },
            self.get_customer_memo_key(),
            self.get_customer_active_key()
        )
        flag_completed(block_num)

        response = self.client.get(url_for('Blockchain.Api.get_balances') + "?take=2")
        assert response.status_code == 200
        self.assertEqual(response.json["items"],
                         [{'address': addressDW, 'assetId': '1.3.0', 'balance': 110000, 'block': block_num * 10}])

        block_num = build_sign_and_broadcast(
            {
                "operationId": "cbeea30e-2218-4405-9089-86d003e4df61",
                "fromAddress": addressDW,
                "toAddress": addressHW,
                "assetId": "1.3.0",
                "amount": 100000,
                "includeFee": True
            },
            utils.get_exchange_memo_key(),
            utils.get_exchange_active_key()
        )

        response = self.client.get(url_for('Blockchain.Api.get_balances') + "?take=2")
        assert response.status_code == 200
        self.assertEqual(response.json["items"][0]["balance"], 10000)
        assert block_num > 0

        balance_block_num = block_num

        response = self.client.get(url_for('Blockchain.Api.get_broadcasted_transaction', operationId="cbeea30e-2218-4405-9089-86d003e4df61"))
        self.assertEqual(response.json["block"], block_num * 10)

        block_num = build_sign_and_broadcast(
            {
                "operationId": "cbeea30e-2218-4405-9089-86d003e4df62",
                "fromAddress": addressHW,
                "toAddress": create_unique_address(self.get_customer_id(), ""),
                "assetId": "1.3.0",
                "amount": 100000,
                "includeFee": True
            },
            utils.get_exchange_memo_key(),
            utils.get_exchange_active_key()
        )
        flag_completed(block_num)

        response = self.client.get(url_for('Blockchain.Api.get_balances') + "?take=2")
        assert response.status_code == 200
        self.assertEqual(response.json["items"],
                         [{'address': addressDW, 'assetId': '1.3.0', 'balance': 10000, 'block': balance_block_num * 10}])

        self.maxDiff = None

        toDW = self.client.get(url_for('Blockchain.Api.get_address_history_to', address=addressDW) + "?take=3")
        assert toDW.status_code == 200
        self.assertEqual(toDW.json,
                         [{'amount': '110000', 'assetId': '1.3.0', 'fromAddress': addressEW, 'hash': toDW.json[0]['hash'], 'timestamp': toDW.json[0]['timestamp'], 'toAddress': addressDW}])

        fromDW = self.client.get(url_for('Blockchain.Api.get_address_history_from', address=addressDW) + "?take=3")
        assert fromDW.status_code == 200
        self.assertEqual(fromDW.json,
                         [{'amount': '100000', 'assetId': '1.3.0', 'fromAddress': addressDW, 'hash': fromDW.json[0]['hash'], 'timestamp': fromDW.json[0]['timestamp'], 'toAddress': 'lykke-test:'}])

        toHW = self.client.get(url_for('Blockchain.Api.get_address_history_to', address=addressHW) + "?take=3")
        assert toHW.status_code == 200
        assert toHW.json == []

        fromHW = self.client.get(url_for('Blockchain.Api.get_address_history_from', address=addressHW) + "?take=3")
        assert fromHW.status_code == 200
        self.assertEqual(fromHW.json,
                         [{'amount': '99900', 'assetId': '1.3.0', 'fromAddress': addressHW, 'hash': fromHW.json[0]['hash'], 'timestamp': fromHW.json[0]['timestamp'], 'toAddress': 'lykke-customer:'}])
