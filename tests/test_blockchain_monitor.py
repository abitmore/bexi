from bexi.blockchain_monitor import BlockchainMonitor
from bexi.connection import requires_blockchain
from bexi import Config, connection
from tests.abstract_tests import ATestnetTest


class TestBlockchainMonitor(ATestnetTest):

    def setUp(self):
        # only load the config we want (no active keys!)
        if Config.data and Config.data["network_type"] != "Test":
            connection.reset()

        Config.load(["config_bitshares_connection.yaml",
                     "config_bitshares_memo_keys.yaml",
                     "config_bitshares.yaml",
                     "config_operation_storage.yaml"])
        Config.data["operation_storage"]["use"] = "mongodbtest"
        Config.data["network_type"] = "Test"
        Config.data["bitshares"]["connection"]["Test"]["nobroadcast"] = True

    def tearDown(self):
        Config.reset()

    @requires_blockchain
    def test_listen(self):
        monitor = BlockchainMonitor()
        monitor.start_block = 14972965
        monitor.stop_block = 14972975
        monitor.listen()
