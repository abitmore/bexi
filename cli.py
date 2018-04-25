#!/usr/bin/env python3
import click
from bexi import Config
from bexi.connection import requires_blockchain

import logging
import threading

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

    monitor = BlockchainMonitor()
    monitor.listen()


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
