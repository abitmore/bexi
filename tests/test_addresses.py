import unittest

from bexi import utils
from bexi.addresses import create_unique_address, split_unique_address


class TestAddresses(unittest.TestCase):

    def test_create_unique_address(self):
        unique_wallet = create_unique_address(
            utils.get_exchange_account_id(),
            lambda: "9ed8c906-d6ab-4fb8-a314-0516a175717a")

        assert unique_wallet == utils.get_exchange_account_id() + ":::9ed8c906-d6ab-4fb8-a314-0516a175717a"

    def test_split_address(self):
        unique_wallet = create_unique_address(
            utils.get_exchange_account_id(),
            lambda: "9ed8c906-d6ab-4fb8-a314-0516a175717a")

        address = split_unique_address(unique_wallet)

        assert address["account_id"] == utils.get_exchange_account_id()


if __name__ == "__main__":
    unittest.main()
