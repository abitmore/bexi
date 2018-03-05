from bexi.wsgi.sign_service import implementations

from tests.abstract_tests import ATestnetTest
from bexi import Config
import json


class TestSignService(ATestnetTest):

    def test_wallets(self):
        address = implementations.create_address()

        if Config.get("bitshares", "keep_keys_private", True):
            assert address["privateKey"] == "keep_keys_private"
        else:
            assert address["privateKey"] == Config.get_config()["bitshares"]["exchange_account_active_key"]
        assert Config.get_config()["bitshares"]["exchange_account_id"] in address["publicAddress"]

    def test_sign(self):
        tx = {
            "ref_block_num": 49506,
            "ref_block_prefix": 2292772274,
            "expiration": "2018-01-25T08:29:00",
            "operations": [
                [
                    2,
                    {
                        "fee": {
                            "amount": 9,
                            "asset_id": "1.3.0"
                        },
                        "fee_paying_account": "1.2.126225",
                        "order": "1.7.49956139",
                        "extensions": []
                    }
                ]
            ],
            "extensions": [],
            "signatures": [],
        }
        stx = implementations.sign(tx, [Config.get_config()["bitshares"]["exchange_account_active_key"]])
        stx = json.loads(stx["signedTransaction"])
        self.assertIn("signatures", stx)
        self.assertEqual(len(stx["signatures"]), 1)

        stx = implementations.sign(
            tx, [Config.get_config()["bitshares"]["exchange_account_active_key"],
                 self.get_customer_active_key()]
        )
        stx = json.loads(stx["signedTransaction"])
        self.assertIn("signatures", stx)
        self.assertEqual(len(stx["signatures"]), 2)
