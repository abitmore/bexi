from bexi.blockchain_monitor import BlockchainMonitor
from bexi.connection import requires_blockchain
from bexi import Config
from tests.abstract_tests import ATestnetTest


class TestBlockchainMonitor(ATestnetTest):

    def setUp(self):
        super(TestBlockchainMonitor, self).setUp()
        Config.data["operation_storage"]["use"] = "mongodbtest"

    def tearDown(self):
        Config.reset()

    @requires_blockchain
    def test_listen(self):
        monitor = BlockchainMonitor()
        monitor.start_block = 2755080
        monitor.stop_block = 2755087
        monitor.listen()
