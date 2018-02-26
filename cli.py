#!/usr/bin/env python3
import click
from bexi.wsgi.app import (
    create_common_app,
    create_basic_flask_app,
    create_manage_service_app,
    create_sign_service_app
)
from bexi import Config, set_global_logger
from bexi.connection import requires_blockchain
from bexi.blockchain_monitor import BlockchainMonitor

app = None
config = None


@click.group()
def main():
    Config.load("config_common.yaml")
    global app
    global config
    config = Config.get_config()["wsgi"]
    app = create_basic_flask_app()
    set_global_logger()


@main.command()
@click.option("--host")
@click.option("--port")
def wsgi(host, port):
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares_memo_keys.yaml",
                 "config_bitshares_active_keys.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])

    host = host or config["host"]
    port = port or config["port"]
    app.logger.info("Starting " + config["name"] + " with all wsgi services ...")
    create_manage_service_app(
        create_sign_service_app(
            create_common_app(app))
    ).run(host=host, port=port, debug=True)


@main.command()
@click.option("--host")
@click.option("--port")
def sign_service(host, port):
    load_sign_service_config()

    host = host or config["host"]
    port = port or config["port"]
    app.logger.info("Starting " + config["name"] + " sign service ...")
    create_sign_service_app(
        create_common_app(app)
    ).run(host=host, port=port)


def load_sign_service_config():
    Config.load(["config_bitshares_memo_keys.yaml",
                 "config_bitshares_active_keys.yaml",
                 "config_bitshares.yaml"])


@main.command()
@click.option("--host")
@click.option("--port")
def manage_service(host, port):
    load_manage_service_config()

    host = host or config["host"]
    port = port or config["port"]
    app.logger.info("Starting " + config["name"] + " manage service ...")
    create_manage_service_app(
        create_common_app(app)
    ).run(host=host, port=port)


def load_manage_service_config():
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares_memo_keys.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])


@main.command()
def blockchain_monitor():
    load_blockchain_monitor_config()

    app.logger.info("Starting BitShares blockchain monitor ...")
    start_block_monitor()


def load_blockchain_monitor_config():
    Config.load(["config_bitshares_connection.yaml",
                 "config_bitshares_memo_keys.yaml",
                 "config_bitshares.yaml",
                 "config_operation_storage.yaml"])


@requires_blockchain
def start_block_monitor():
    monitor = BlockchainMonitor()
#     monitor.start_block = 15290125
    monitor.listen()


@main.command()
def dump_configs():
    load_sign_service_config()
    Config.dump_current("config_sign_service.json")

    Config.reset()

    Config.load("config_common.yaml")
    load_manage_service_config()
    Config.dump_current("config_manage_service.json")

    Config.reset()

    Config.load("config_common.yaml")
    load_blockchain_monitor_config()
    Config.dump_current("config_blockchain_monitor.json")

    print("JSon configuration files for sign_service, manage_service and blockchain_monitor written to dump folder")


main()
