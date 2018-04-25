from ..operation_storage.exceptions import DuplicateOperationException
from ..factory import get_operation_storage
from ..connection import requires_blockchain
from .. import Config

from bitshares.account import Account
from bitshares.blockchain import Blockchain
from bitshares.exceptions import WalletLocked, MissingKeyError
from bitshares.instance import shared_bitshares_instance
from bitshares.memo import Memo
from bitsharesbase.operationids import getOperationNameForId
from bitsharesbase.signedtransactions import Signed_Transaction
import logging


class BlockchainMonitor(object):
    """ The BlockchainMonitor Class is used to listen to the BitShares blockchain
        and react on transfers to the monitored account (as per the configuration)

        :param bitshares.bitshares.BitShares bitshares_instance: (optional)
            Instance of ``Bitshares()``. Uses pybitshares internal
            configuration as default
        :param int start_block: First block to look at
        :param int last_block: Last block to look at

        When instantiating, the object

        1. obtains a storage object from the factory
        2. obtains data about the exchange account name from the blockchain

        .. note:: This object requires that either WIF keys for the memo
            decoding are manually provided through ``bitshares_instance``, or
            that the BitShares wallet is unlocked with a passphrase using the
            `.unlock_wallet(pwd)` method.

        An object, when listening (see below) will parse all blocks, with all
        transactions, with all operations and only post-process those that
        match our criteria (e.g. transfers from or to the exchange account).
        Post processing, by default, calls the storage and inserts the
        operation.

        **Examples**:

        .. code-block:: python

            from bexi.blockchain_monitor import BlockchainMonitor
            from getpass import getpass
            chain = BlockchainMonitor()
            chain.unlock_wallet(getpass())
            chain.listen()

        .. code-block:: python

            from bexi.blockchain_monitor import BlockchainMonitor
            from bitshares import BitShares
            bitshares = BitShares(
                "ws://trusted_local_node:8090",
                keys=["5JXJRwRffFu4xFZTiicXHehyq22MSUL3TmKoP2wHZMUg3tVum4Q"]
            )
            chain = BlockchainMonitor(bitshares_instance=bitshares)
            chain.listen()

    """

    @requires_blockchain
    def __init__(
        self,
        *args,
        bitshares_instance=None,
        **kwargs
    ):
        # BitShares instance
        self.bitshares = bitshares_instance or shared_bitshares_instance()

        # make sure the memo key is added to the instance
        memo_key = Config.get("bitshares", "exchange_account_memo_key")
        if not self.bitshares.wallet.created() or\
                memo_key in self.bitshares.wallet.keys:
            self.bitshares.wallet.setKeys(memo_key)

        # Get configuration
        self.config = Config.get_config()

        # The watch_mode tells us where to look at "recent" blocks in the
        # blockchain
        self.watch_mode = self.config["bitshares"].get(
            "watch_mode", "irreversible")

        # Storage factory
        self.storage = kwargs.pop("storage", None)
        if not self.storage:
            self.storage = get_operation_storage(
                self.config["operation_storage"]["use"]
            )

        # Obtain data from the Blockchain about our account
        self.my_account = Account(
            self.config["bitshares"]["exchange_account_name"],
            bitshares_instance=self.bitshares
        )

        # Test my_account
        assert self.my_account["id"] == self.config["bitshares"]["exchange_account_id"], (
            "account id for exchange_account_name does not match exchange_acount_id! "
            "({} != {})".format(
                self.my_account["id"],
                self.config["bitshares"]["exchange_account_id"]
            )
        )

        # More (optional) parameters provided on instantiation
        self.start_block = kwargs.pop("start_block", None)
        self.stop_block = kwargs.pop("stop_block", None)

    def unlock_wallet(self, pwd):
        """ Unlock the pybitshares wallet with the provided password
        """
        self.bitshares.wallet.unlock(pwd)
        return self

    def listen(self):
        """ Listen to the blockchain and send blocks to
            :func:`BlockchainMonitor.process_block`

            .. note:: Depending on the setting of ``watch_mode`` in the
                configuration, the listen method has slightly different
                behavior. Namely, we here have the choice between "head" (the
                last block) and "irreversible" (the block that is confirmed by
                2/3 of all block producers and is thus irreversible)
        """
        last_block = self.storage.get_last_head_block_num()

        logging.getLogger(__name__).debug("Start listen with start=" + str(self.start_block) + " stop=" + str(self.stop_block) + " last=" + str(last_block))

        # if set to true, block numbers may not be consecutively
        self.allow_block_jump = False

        if not self.start_block:
            if last_block > 0:
                self.start_block = last_block + 1
        else:
            if not self.start_block == self.storage.get_last_head_block_num() + 1:
                # allow first block to jump
                self.allow_block_jump = True
                logging.getLogger(__name__).warning("Force listen with different block than last in storage (storage=" + str(last_block) + ", given=" + str(self.start_block) + ")")

        retry = True
        while (retry):
            retry = False
            for block in Blockchain(
                mode=self.watch_mode,
                max_block_wait_repetition=12,
                bitshares_instance=self.bitshares
            ).blocks(
                start=self.start_block,
                stop=self.stop_block
            ):
                logging.getLogger(__name__).debug("Processing block " + str(block["block_num"]))

                last_head_block = self.storage.get_last_head_block_num()

                if last_head_block == 0 or\
                        block["block_num"] == last_head_block + 1 or\
                        (self.allow_block_jump and last_head_block < block["block_num"]):
                    self.allow_block_jump = False
                    # no blocks missed
                    self.process_block(block)
                    self.storage.set_last_head_block_num(block["block_num"])
                elif block["block_num"] == last_head_block:
                    # possible on connection error, skip block
                    continue
                else:
                    self.start_block = last_head_block + 1
                    if self.start_block > self.stop_block:
                        logging.getLogger(__name__).error("Block was missed, or trying to march backwards. Stop block already reached, shutting down ...")
                    else:
                        logging.getLogger(__name__).error("Block was missed, or trying to march backwards. Retry with next block " + str(last_head_block + 1))
                        retry = True

    def process_block(self, block):
        """ Process block and send transactions to
            :func:`BlockchainMonitor.process_transaction`

            :param dict block: Individual block as dictionary

            This method takes all transactions (appends block-specific
            informations) and sends them to transaction processing
        """
        for transaction in block.get("transactions", []):
            # Add additional information
            transaction.update({
                "block_num": block.get("block_num"),
                "timestamp": block.get("timestamp"),
            })
            self.process_transaction(transaction)

    def process_transaction(self, transaction):
        """ Process transaction and send operations to
            :func:`BlockchainMonitor.process_operation`

            :param dict transaction: Individual transaction as dictionary

            This method takes a transaction (appends transaction-specific
            informations) and sends all operations in it to operation
            processing
        """
        def get_tx_id(transaction):
            """ This method is used as a *getter* that is handed over as lambda function
                so we don't need to derive transaction ids for every
                transaction but instead only obtain the transaction id on those
                transactions that contain operations that we are interested in.
            """
            if self.bitshares.prefix != "BTS":
                transaction["operations"][0][1].update({"prefix": self.bitshares.prefix})

            tx = Signed_Transaction(**transaction)
            return tx.id

        for op_in_tx, operation in enumerate(transaction.get("operations", [])):
            # op_in_tx tells us which operation in the transaction we are
            # talking about. Technically, multiple deposits could be made in a
            # single transaction. This is why we need to ensure we can
            # distinguish them.
            self.process_operation(
                {
                    "block_num": transaction.get("block_num"),
                    "timestamp": transaction.get("timestamp"),
                    "expiration": transaction.get("expiration"),
                    "op_in_tx": op_in_tx,
                    "op": [
                        # Decode the operation type id as string
                        getOperationNameForId(operation[0]),
                        # Operation payload
                        operation[1]
                    ],
                },
                # This is a getter lambda that allows us to obtain a
                # transaction id for a transaction but allows us to only derive
                # it for those transactions that contain operations of
                # interest.
                tx_id_getter=(lambda: get_tx_id(transaction))
            )

    def operation_matches(self, operation):
        """ This method defines the conditions that need to be met so we send
            an operation forward to the post processing
        """
        operation_type = operation["op"][0]
        payload = operation["op"][1]
        if (
            operation_type == "transfer" and (
                payload["from"] == self.my_account["id"] or
                payload["to"] == self.my_account["id"]
            )
        ):
            return True
        return False

    def decode_memo(self, payload):
        """ This method decodes the memo for us.

            .. note:: Three cases exist that prevent us from decoding a memo
                that lead to a special message being used instead:

                * ``memo_key_missing``: In the case the decryption key was not provided
                * ````: In the case no memo was provided
                * ``decoding_not_possible``: In the case, the memo couldn't be decrypted

        """
        try:
            decoded_memo = Memo(
                bitshares_instance=self.bitshares
            ).decrypt(payload["memo"])
        except MissingKeyError:
            decoded_memo = "memo_key_missing"
        except KeyError:
            decoded_memo = ""
        except ValueError:
            decoded_memo = "decoding_not_possible"
        return decoded_memo

    def process_operation(self, operation, tx_id_getter):
        """ Process operation and send results to
            :func:`BlockchainMonitor.postprocess_operation`

            :param dict operation: Individual operation as dictionary
            :param func tx_id_getter: a lambda that allows us to obtain the
                transaction id if we are interested in one or more operations
                within

            This method takes an operation (appends transaction-specific
            informations) and figures out if it is interesting to us. If so, it
            will send it to postprocess_operation().

        """

        if not self.operation_matches(operation):
            return

        operation.update({
            "transaction_id": tx_id_getter(),
        })

        self.postprocess_operation(operation)

    def postprocess_operation(self, operation):
        """ This method only obtains operations that are relevant for us.
            It tries to decode the memo and sends all the relevant information
            to the storage for insertion into the database.

            :param dict operation: operation as dictionary
        """
        payload = operation["op"][1]
        operation.update({
            "from_name": Account(
                payload["from"],
                bitshares_instance=self.bitshares
            )["name"],
            "to_name": Account(
                payload["to"],
                bitshares_instance=self.bitshares
            )["name"],
            "decoded_memo": self.decode_memo(payload),
        })

        logging.getLogger(__name__).debug("Recognized accounts, inserting transfer " + str(operation["transaction_id"]))

        try:
            self.storage.insert_or_update_operation(operation)
        except DuplicateOperationException:
            logging.getLogger(__name__).debug("Storage already contained operation, skipping ...")
