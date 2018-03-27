#!/usr/bin/env python3
import click
from bexi.wsgi.app import (
    get_manage_service_app,
    get_sign_service_app,
    get_blockchain_monitor_service_app
)
from bexi import Config
from bexi.connection import requires_blockchain
from bexi.blockchain_monitor import BlockchainMonitor
import logging

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

    app = get_manage_service_app()
    get_sign_service_app(app)
    app.logger.info("Starting " + config["name"] + " with manage and sign service ...")
    app.run(host=host, port=port, debug=True)


@main.command()
@click.option("--host")
@click.option("--port")
def sign_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    app = get_sign_service_app()
    app.logger.info("Starting " + config["name"] + " sign service ...")
    app.run(host=host, port=port)


@main.command()
@click.option("--host")
@click.option("--port")
def manage_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    app = get_manage_service_app()
    app.logger.info("Starting " + config["name"] + " manage service ...")
    app.run(host=host, port=port)


@main.command()
def blockchain_monitor():
    load_blockchain_monitor_config()

    logging.getLogger(__name__).info("Starting BitShares blockchain monitor ...")
    start_block_monitor()


def load_blockchain_monitor_config():
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares_memo_keys.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])


@main.command()
@click.option("--host")
@click.option("--port")
def blockchain_monitor_service(host, port):
    host = host or config["host"]
    port = port or config["port"]

    app = get_blockchain_monitor_service_app()
    app.logger.info("Starting " + config["name"] + " blockchain monitor service ...")
    app.run(host=host, port=port)


@requires_blockchain
def start_block_monitor():
    monitor = BlockchainMonitor()
#     monitor.start_block = 15290125
    monitor.listen()


@main.command()
def dump_configs():
    get_sign_service_app()
    Config.dump_current("config_sign_service.json")

    Config.reset()

    Config.load("config_common.yaml")
    get_manage_service_app()
    Config.dump_current("config_manage_service.json")

    Config.reset()

    Config.load("config_common.yaml")
    load_blockchain_monitor_config()
    Config.dump_current("config_blockchain_monitor.json")

    Config.reset()

    Config.load("config_common.yaml")
    get_blockchain_monitor_service_app()
    Config.dump_current("config_blockchain_monitor_service.json")

    print("JSon configuration files for sign_service, manage_service and blockchain_monitor written to dump folder")


main()
