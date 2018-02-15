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


def check_keys():
    if not Config.get_config()["bitshares"]["exchange_account_name"]:
        raise Exception("Please set the exchange account name in config.yaml")
    if not Config.get_config()["bitshares"]["exchange_account_id"]:
        raise Exception("Please set the exchange account id in config.yaml")
    if not Config.get_config()["bitshares"]["exchange_account_active_key"]:
        raise Exception("Please set the active key of the exchange account in config.yaml.")


@click.group()
def main():
    global app
    global config
    app = create_basic_flask_app()
    config = Config.get_config()["wsgi"]
    set_global_logger()
    check_keys()


@main.command()
@click.option("--host")
@click.option("--port")
def wsgi(host, port):
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
    host = host or config["host"]
    port = port or config["port"]
    app.logger.info("Starting " + config["name"] + " manage service ...")
    create_manage_service_app(
        create_common_app(app)
    ).run(host=host, port=port)


@main.command()
def blockchain_monitor():
    app.logger.info("Starting BitShares blockchain monitor ...")
    start_block_monitor()


@requires_blockchain
def start_block_monitor():
    monitor = BlockchainMonitor()
#     monitor.start_block = 14972965
    monitor.listen()


main()
