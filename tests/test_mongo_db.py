'''
Created on Jan 18, 2018

@author: schiessl
'''
import unittest
import pymongo
from pymongo import MongoClient

from bexi import Config
from bexi.operation_storage.interface import OperationStorageLostException
from bexi.operation_storage.mongodb_storage import MongoDBOperationsStorage


class TestMongoDB(unittest.TestCase):

    def setUp(self):
        Config.load()

    def _get_db_config(self):
        config = Config.get_config()["operation_storage"]
        mongodb_config = config["mongodbtest"]
        mongodb_config["operation_collection"] = mongodb_config.get("operation_collection", "operations")
        return mongodb_config

    def test_not_reachable(self):
        mongodb_config = self._get_db_config()
        mongodb_config["seeds"] = ["unreachable:1234"]
        client = MongoClient(host=mongodb_config["seeds"],
                             socketTimeoutMS=100,
                             connectTimeoutMS=100,
                             serverSelectionTimeoutMS=100,
                             waitQueueTimeoutMS=100,
                             heartbeatFrequencyMS=500
                             )
        self.assertRaises(
            pymongo.errors.ServerSelectionTimeoutError,
            client[mongodb_config["db"]][mongodb_config["operation_collection"]].drop
        )

    def test_not_reachable_via_os(self):
        mongodb_config = Config.get_config()["operation_storage"]["mongodbtest"]
        mongodb_config["seeds"] = ["unreachable:1234"]
        client = MongoClient(host=mongodb_config["seeds"],
                             socketTimeoutMS=100,
                             connectTimeoutMS=100,
                             serverSelectionTimeoutMS=100,
                             waitQueueTimeoutMS=100,
                             heartbeatFrequencyMS=500
                             )
        self.assertRaises(
            OperationStorageLostException,
            MongoDBOperationsStorage,
            mongodb_config=mongodb_config,
            mongodb_client=client
        )

    def test_is_running(self):
        mongodb_config = self._get_db_config()
        client = MongoClient(host=mongodb_config["seeds"])
        client[mongodb_config["db"]][mongodb_config["operation_collection"]]

    def test_store(self):
        mongodb_config = self._get_db_config()
        client = MongoClient(host=mongodb_config["seeds"])
        db = client[mongodb_config["db"]]
        collection = db["test_collection"]

        collection.drop()

        import datetime
        date_now = datetime.datetime.utcnow()
        date_now = date_now.replace(
            microsecond=int(date_now.microsecond/1000)*1000)
        post = {"author": "Mike",
                "text": "My first blog post!",
                "tags": ["mongodb", "python", "pymongo"],
                "date": date_now}

        collection.insert_one(post)

        assert "test_collection" in\
            db.collection_names(include_system_collections=False)

        assert collection.find_one()["date"] == date_now

    def test_update(self):
        mongodb_config = self._get_db_config()
        client = MongoClient(host=mongodb_config["seeds"])
        db = client[mongodb_config["db"]]
        collection = db["test_collection"]
        collection.drop()

        collection.update_one(
            {"status": "last_head_block_num",
             "last_head_block_num": 5},
            {'$inc': {'last_head_block_num': 1}},
            upsert=True)

        collection.update_one(
            {"status": "last_head_block_num"},
            {'$inc': {'last_head_block_num': 1}},
            upsert=True)

        status = collection.find_one({"status": "last_head_block_num"})
        assert status["last_head_block_num"] == 7

    def test_index(self):
        mongodb_config = self._get_db_config()
        client = MongoClient(host=mongodb_config["seeds"])
        db = client[mongodb_config["db"]]
        db["test_collection"].drop()
        collection = db.create_collection(
            "test_collection",
            validator={
                "$jsonSchema": {
                    "type": "object",
                    "required": ["custom_index", "content"],
                    "properties": {
                        "custom_index": {
                            "type": "number",
                            "description": "must be an int and is required"
                        },
                        "content": {
                            "type": "string",
                            "description": "must be a string and is required"
                        }
                    }
                }
            })

        collection.create_index([('custom_index', pymongo.ASCENDING)],
                                unique=True)

        valid = {"custom_index": 1,
                 "content": "nothing"}

        also_valid = {"custom_index": 2,
                      "content": "nothing"}

        invalid_empty = {"content": "nothing"}

        invalid_overflow = {"custom_index": 9999900000,
                            "content": "nothing"}

        collection.insert_one(valid)
        collection.insert_one(also_valid)
        collection.insert_one(invalid_overflow)

        self.assertRaises(pymongo.errors.WriteError,
                          collection.insert_one,
                          invalid_empty)

        # second time has to fail due to uniqueness
        self.assertRaises(pymongo.errors.WriteError,
                          collection.insert_one,
                          also_valid)


if __name__ == "__main__":
    unittest.main()
