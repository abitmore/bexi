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
    Config.load("config_bitshares_connection.yaml")
    Config.load("config_bitshares_keys.yaml")
    Config.load("config_bitshares.yaml")
    Config.load("config_operation_storage.yaml")

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
    Config.load("config_bitshares_keys.yaml")
    Config.load("config_bitshares.yaml")

    host = host or config["host"]
    port = port or config["port"]
    app.logger.info("Starting " + config["name"] + " sign service ...")
    create_sign_service_app(
        create_common_app(app)
    ).run(host=host, port=port)


@main.command()
@click.option("--host")
@click.option("--port")
def manage_service(host, port):
    Config.load("config_bitshares_connection.yaml")
    Config.load("config_bitshares.yaml")
    Config.load("config_operation_storage.yaml")

    host = host or config["host"]
    port = port or config["port"]
    app.logger.info("Starting " + config["name"] + " manage service ...")
    create_manage_service_app(
        create_common_app(app)
    ).run(host=host, port=port)


@main.command()
def blockchain_monitor():
    Config.load("config_bitshares_connection.yaml")
    Config.load("config_bitshares.yaml")
    Config.load("config_operation_storage.yaml")

    app.logger.info("Starting BitShares blockchain monitor ...")
    start_block_monitor()


@requires_blockchain
def start_block_monitor():
    monitor = BlockchainMonitor()
#     monitor.start_block = 14972965
    monitor.listen()


main()
