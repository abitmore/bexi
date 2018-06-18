""" This module collects all business logic that is used in the routes of the corresponding blueprint
    in :mod:`.views`.
"""
from ...connection import requires_blockchain
from ... import Config, factory, __VERSION__
from ...wsgi import flask_setup

import json
from datetime import datetime, timedelta


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

    issueIndicators = None
    if last_block_stored != 0 and last_block_stored < last_block - 5:
        issueIndicators = [
            {"type": "unknown",
             "value": "Blockchain Monitor out of sync"}
        ]

    blockchain_time = datetime.strptime(
        bitshares_instance.rpc.get_dynamic_global_properties().get("time"), "%Y-%m-%dT%H:%M:%S"
    )

    delayed_blockchain_time = (
        blockchain_time +
        timedelta(seconds=Config.get("bitshares", "blockchain_allowed_sync_delay_in_sec", 180)))

    if delayed_blockchain_time < datetime.now():
        if issueIndicators is None:
            issueIndicators = []
        issueIndicators.append({
            "type": "unknown",
            "value": "Blockchain is stuck in the past: Chain time is " + str(blockchain_time) + ", server time is " + str(datetime.now())})

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
    if issueIndicators is not None:
        info["issueIndicators"] = issueIndicators

    return info
