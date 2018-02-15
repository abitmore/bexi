import unittest

from bexi.blockchain_monitor import BlockchainMonitor
from bexi.connection import requires_blockchain
from bexi import Config


class TestBlockchainMonitor(unittest.TestCase):

    def setUp(self):
        Config.load()
        Config.data["operation_storage"]["use"] = "mongodbtest"
        Config.data["network_type"] = "Test"

    def tearDown(self):
        Config.reset()

    @requires_blockchain
    def test_listen(self):
        monitor = BlockchainMonitor()
        monitor.start_block = 2755080
        monitor.stop_block = 2755087
        monitor.listen()
