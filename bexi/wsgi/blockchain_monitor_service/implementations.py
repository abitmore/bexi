""" This module collects all business logic that is used in the routes of the corresponding blueprint
    in :mod:`.views`.
"""
from ...connection import requires_blockchain
from ... import Config, factory, __VERSION__
from ...wsgi import flask_setup
import json


class BlockChainMonitorOutOfSyncExcpetion(Exception):
    pass


operation_storage = None


def _get_os(storage=None):
    global operation_storage
    if storage:
        operation_storage = storage

    if not operation_storage:
        operation_storage = factory.get_operation_storage()

    return operation_storage


@requires_blockchain
def isalive(bitshares_instance):
    last_block = bitshares_instance.rpc.get_dynamic_global_properties().get("last_irreversible_block_num")
    last_block_stored = _get_os().get_last_head_block_num()

    if last_block_stored != 0 and last_block_stored < last_block - 5:
        raise BlockChainMonitorOutOfSyncExcpetion(json.dumps(
            {
                "description": "Blockchain Monitor out of sync",
                "last_processed": last_block_stored,
                "last_irreversible_block_num": last_block
            }
        ))

    info = {
        "name": Config.get("wsgi", "name"),
        "version": __VERSION__,
        "env": flask_setup.get_env_info(),
        "isDebug": flask_setup.is_debug_on(),
        "contractVersion": "1.1.3",
        "status": {
            "last_processed": last_block_stored,
            "last_irreversible_block_num": last_block}
    }

    return info
