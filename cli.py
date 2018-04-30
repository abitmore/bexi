#!/usr/bin/env python3
import click
import time
from bexi import Config, factory
from bexi.connection import requires_blockchain

import logging
import threading
import json
from pprint import pprint
from bexi.operation_storage.exceptions import OperationNotFoundException

config = Config.get("wsgi")


@click.group()
def main():
    pass


@main.command()
@click.option("--host")
@click.option("--port")
def wsgi(host, port):
    host = host or config["host"]
    port = port or config["port"]

    from bexi.wsgi.app import get_manage_service_app, get_sign_service_app

    app = get_manage_service_app()
    app = get_sign_service_app(app)
    app.logger.info("Starting " + config["name"] + " with manage and sign service ...")
    app.run(host=host, port=port, debug=True)


@main.command()
@click.option("--host")
@click.option("--port")
def sign_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    from bexi.wsgi.app import get_sign_service_app

    app = get_sign_service_app()
    app.logger.info("Starting " + config["name"] + " sign service ...")
    app.run(host=host, port=port)


@main.command()
@click.option("--host")
@click.option("--port")
def manage_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    from bexi.wsgi.app import get_manage_service_app

    app = get_manage_service_app()
    app.logger.info("Starting " + config["name"] + " manage service ...")
    app.run(host=host, port=port)


@main.command()
@click.option("--host")
@click.option("--port")
def blockchain_monitor_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    from bexi.wsgi.app import get_blockchain_monitor_service_app

    app = get_blockchain_monitor_service_app()

    logging.getLogger(__name__).info("Starting BitShares blockchain monitor as coroutines ...")

    thr = threading.Thread(target=start_block_monitor, daemon=True)
    thr.start()  # run in background

    app.logger.info("Starting " + config["name"] + " blockchain monitor service ...")
    app.run(host=host, port=port)


@main.command()
def only_blockchain_monitor():
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares_memo_keys.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])
    logging.getLogger(__name__).info("Starting BitShares blockchain monitor ...")
    start_block_monitor()


@main.command()
@click.option("--host")
@click.option("--port")
def only_blockchain_monitor_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    from bexi.wsgi.app import get_blockchain_monitor_service_app

    app = get_blockchain_monitor_service_app()
    app.logger.info("Starting " + config["name"] + " blockchain monitor service ...")
    app.run(host=host, port=port)


@requires_blockchain
def start_block_monitor():
    from bexi.blockchain_monitor import BlockchainMonitor
    while (True):
        try:
            monitor = BlockchainMonitor()
            monitor.listen()
        except Exception as e:
            logging.getLogger(__name__).info("Blockchain monitor failed, exception below. Retrying after sleep")
            logging.getLogger(__name__).exception(e)
            time.sleep(1.5)


@main.command()
@click.option("--txid")
@click.option("--customerid")
@click.option("--contains")
@click.option("--status")
@click.option("--incidentid")
def find(txid, customerid, contains, status, incidentid):
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])

    storage = factory.get_operation_storage()

    def get_all():
        return (storage.get_operations_completed() +
                storage.get_operations_in_progress() +
                storage.get_operations_failed())
    operations = []

    if contains:
        for op in get_all():
            print(op)
            if status is not None and not status == op["status"]:
                continue

            if contains in str(op):
                operations.append(op)

    if incidentid:
            for op in list(storage._service.query_entities(
                    storage._operation_tables["incident"])):
                if incidentid in str(op):
                    operations.append(op)

    print("---------- finding transfers ---------------")
    print("found: " + str(len(operations)))

    for op in operations:
        pprint(op)


@main.command()
@click.option("--take")
def balance(take=100):
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])

    pprint(factory.get_operation_storage().get_balances(take))


@main.command()
@click.option("--take")
def balance_calc(take=100):
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])

    pprint(factory.get_operation_storage()._get_balances_recalculate(take))


@main.command()
def tracked():
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])

    storage = factory.get_operation_storage()

    pprint(list(storage._service.query_entities(storage._azure_config["address_table"] + "balance")))


# @main.command()
# def yaml_to_json():
#     os.environ["SettingsUrl"] = None
#     os.environ["PrivateKey"] = None
# 
#     Config.reset()
# 
#     Config.load("config_common.yaml")
#     get_sign_service_app()
#     Config.dump_current("config_sign_service.json")
# 
#     Config.reset()
# 
#     Config.load("config_common.yaml")
#     get_manage_service_app()
#     Config.dump_current("config_manage_service.json")
# 
#     Config.reset()
# 
#     Config.load("config_common.yaml")
#     load_blockchain_monitor_config()
#     Config.dump_current("config_blockchain_monitor.json")
# 
#     Config.reset()
# 
#     Config.load("config_common.yaml")
#     get_blockchain_monitor_service_app()
#     Config.dump_current("config_blockchain_monitor_service.json")
# 
#     print("JSon configuration files for sign_service, manage_service and blockchain_monitor written to dump folder")


main()
