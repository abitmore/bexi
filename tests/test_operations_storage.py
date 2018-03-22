from tests.abstract_tests import ATestOperationStorage

from bexi.operation_storage.interface import AddressAlreadyTrackedException,\
    AddressNotTrackedException, NoBlockNumException, StatusInvalidException,\
    InvalidOperationException, OperationNotFoundException,\
    DuplicateOperationException

from bexi.addresses import create_unique_address, split_unique_address
from bexi.factory import get_operation_storage
from jsonschema.exceptions import ValidationError


class TestMongoOperationStorage(ATestOperationStorage):

    def setUp(self):
        super(TestMongoOperationStorage, self).setUp()
        self.storage = get_operation_storage("mongodbtest")

    def test_insert_and_complete(self):
        filled_operation = self.get_in_progress_op()

        self.storage.insert_operation(filled_operation)

        self.assertRaises(NoBlockNumException,
                          self.storage.flag_operation_completed,
                          filled_operation)

        filled_operation = self.get_completed_op()
        filled_operation["chain_identifier"] = "doesnt_exist"
        self.assertRaises(OperationNotFoundException,
                          self.storage.flag_operation_completed,
                          filled_operation)

        filled_operation = self.get_completed_op()
        self.storage.flag_operation_completed(filled_operation)

        filled_operation["status"] = "in-progress"
        self.assertRaises(StatusInvalidException,
                          self.storage.flag_operation_completed,
                          filled_operation)

        assert len(self.storage.get_operations_in_progress()) == 0
        assert len(self.storage.get_operations_completed()) == 1

        for document in self.storage.get_operations_completed():
            assert document["chain_identifier"] == self.get_completed_op()["chain_identifier"]

    def test_insert(self):
        filled_operation = self.get_in_progress_op()
        self.storage.insert_operation(filled_operation)

        filled_operation = self.get_completed_op()
        filled_operation["chain_identifier"] = "some_other_chain_identifier_1"
        filled_operation["incident_id"] = "some_other_incident_id"
        self.storage.insert_operation(filled_operation)

        self.assertRaises(DuplicateOperationException,
                          self.storage.insert_operation,
                          filled_operation)

        assert len(self.storage.get_operations_in_progress()) == 1
        assert len(self.storage.get_operations_completed()) == 1

        for document in self.storage.get_operations_in_progress():
            assert document["incident_id"] ==\
                self.get_in_progress_op()["incident_id"]

    def test_get_operation(self):
        filled_operation = self.get_in_progress_op()
        filled_operation["incident_id"] = "some_other_chain_identifier_1"
        self.storage.insert_operation(filled_operation)

        operation = self.storage.get_operation(filled_operation["incident_id"])
        operation.pop("status")
        operation.pop("timestamp")

        self.assertRaises(OperationNotFoundException,
                          self.storage.get_operation,
                          "doesntexist")

        assert operation == filled_operation

    def test_insert_wrong_status(self):
        filled_operation = self.get_completed_op()

        filled_operation["status"] = "in-progress"
        self.assertRaises(ValidationError,
                          self.storage.insert_operation,
                          filled_operation)

        filled_operation["status"] = "in_progress"
        self.assertRaises(InvalidOperationException,
                          self.storage.insert_operation,
                          filled_operation)

        filled_operation["status"] = "completed"
        filled_operation["chain_identifier"] = None
        self.assertRaises(ValidationError,
                          self.storage.insert_operation,
                          filled_operation)

    def test_delete(self):
        self.storage.insert_operation(self.get_in_progress_op())
        self.storage.flag_operation_completed(self.get_completed_op())

        operations = self.storage.get_operations_completed()

        assert len(operations) == 1

        self.storage.delete_operation(operations[0])

        self.assertRaises(OperationNotFoundException,
                          self.storage.delete_operation,
                          operations[0])

        assert len(self.storage.get_operations_in_progress()) == 0
        assert len(self.storage.get_operations_completed()) == 0

        filled_operation = self.get_in_progress_op()
        filled_operation["incident_id"] = "some_other_chain_identifier_1"
        self.storage.insert_operation(filled_operation)

        self.storage.delete_operation(filled_operation["incident_id"])

        assert len(self.storage.get_operations_in_progress()) == 0

    def test_get_balance(self):
        address = create_unique_address("some_user_1")
        addrs = split_unique_address(address)
        asset = "BTS_test"

        filled_operation = self.get_completed_op()
        filled_operation["to"] = addrs["account_id"]
        filled_operation["amount_asset_id"] = asset
        filled_operation["customer_id"] = addrs["customer_id"]

        filled_operation["incident_id"] = "some_operation_id_1"
        filled_operation["chain_identifier"] = "some_chain_identifier_1"
        filled_operation["amount_value"] = 10
        self.storage.insert_operation(filled_operation)

        filled_operation["incident_id"] = "some_operation_id_2"
        filled_operation["chain_identifier"] = "some_chain_identifier_2"
        filled_operation["amount_value"] = 20
        self.storage.insert_operation(filled_operation)

        filled_operation["incident_id"] = "some_operation_id_3"
        filled_operation["chain_identifier"] = "some_chain_identifier_3"
        filled_operation["amount_value"] = -5
        self.storage.insert_operation(filled_operation)

        filled_operation["from"] = addrs["account_id"]
        filled_operation["to"] = "some_user"

        filled_operation["incident_id"] = "some_operation_id_4"
        filled_operation["chain_identifier"] = "some_chain_identifier_4"
        filled_operation["amount_value"] = 7
        self.storage.insert_operation(filled_operation)

        balances = self.storage.get_balances(address)

        assert balances[address][asset] == 18

    def test_tracking(self):
        address1 = create_unique_address("user_1")
        address2 = create_unique_address("user_2")
        addr2s = split_unique_address(address2)

        self.storage.track_address(address1)

        self.assertRaises(AddressAlreadyTrackedException,
                          self.storage.track_address,
                          address1)

        self.storage.track_address(address2)

        filled_operation = self.get_completed_op()
        filled_operation["to"] = addr2s["account_id"]
        filled_operation["customer_id"] = addr2s["customer_id"]
        filled_operation["amount_asset_id"] = "TEST"
        filled_operation["amount_value"] = 1234
        self.storage.insert_operation(filled_operation)

        balances = self.storage.get_balances()

        assert address1 not in balances.keys()
        assert address2 in balances.keys()
        assert balances[address2]["TEST"] == 1234

        self.storage.untrack_address(address1)

        self.assertRaises(AddressNotTrackedException,
                          self.storage.untrack_address,
                          address1)

    def test_last_head_blockincrement(self):
        self.storage.set_last_head_block_num(1)
        self.storage.set_last_head_block_num(2)

        assert self.storage.get_last_head_block_num() == 2

    def test_last_head_blockmarching_backwards(self):
        self.storage.set_last_head_block_num(1)
        self.storage.set_last_head_block_num(2)

        self.assertRaises(Exception,
                          self.storage.set_last_head_block_num,
                          1)

    def test_default(self):
        assert self.storage.get_last_head_block_num() == 0


class TestAzureOperationStorageFactory(TestMongoOperationStorage):

    def setUp(self):
        super(TestAzureOperationStorageFactory, self).setUp()
        self.storage = get_operation_storage("azuretest")

