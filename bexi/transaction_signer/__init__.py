from bitsharesbase.signedtransactions import Signed_Transaction


def sign_transaction(transaction, wifs):
    """ This methed signs a raw/unsigned transaction with the provided private
        keys.

        .. note:: The method does not guarantee that the blockchain will accept
            the signed transaction. This may happen in multiple cases, such as
            a) signed with irrelevant or redundant private keys, b)
            insufficient permissions to perform what is requested in the
            operations.

        .. note:: This method does **not** have a connection to the blockchain.
            Hence, neither the expiration, nor any of the TaPOS parameters
            (``ref_block_num``, nor ``ref_block_prefix``) are obtained here.
            The method needs to be provided with a fully valid (but unsigned
            transaction).

        An unsigned transaction takes the following form:

        .. code-block: js

            {
                "ref_block_num": 49506,
                "ref_block_prefix": 2292772274,
                "expiration": "2018-01-25T08:29:00",
                "operations": [[
                    2, {
                        "fee": {
                            "amount": 9,
                            "asset_id": "1.3.0"},
                        "fee_paying_account": "1.2.126225",
                        "order": "1.7.49956139",
                        "extensions": []}]],
                "extensions": [],
                "signatures": [],
            }

        The operation (here, operation type (0) is a ``transfer``) is the
        actual action that should take place on the blockchain. The parameters
        around it are required for a valid transaction and need to be obtained
        outside this method.


        For sake of completion, we here describe how the ``ref_block_num`` and
        ``ref_block_prefix`` are obtained from the blockchain
        (`github <https://github.com/xeroc/python-graphenelib/blob/master/graphenebase/transactions.py#L18-L26>`_):

        .. code-block:: python

            dynBCParams = rpc.get_dynamic_global_properties()
            ref_block_num = dynBCParams["head_block_number"] & 0xFFFF
            ref_block_prefix = struct.unpack_from("<I", unhexlify(dynBCParams["head_block_id"]), 4)[0]

        .. important:: The expiration **must not** be more than 1 day in the future!

        :param dict transaction: unsigned transaction
        :param list wifs: list of private keys in wif format
        :rtype: dict
        :returns: signed transaction

    """
    # Instantiate Signed_Transaction with content
    assert isinstance(transaction, dict)
    assert isinstance(wifs, (list, tuple, set))
    tx = Signed_Transaction(**transaction)
    # call transaction signer
    result = tx.sign(wifs).json()
    result["transaction_id"] = tx.id
    return result
