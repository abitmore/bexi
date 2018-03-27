Manage service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The manage services is started as shown below

.. code-block:: bash

	$ python3 cli.py manage_service
	
The manage service talks to the operation store and the blockchain. It tracks user balance and
transaction history, and does build transaction. When building transaction the memo key of the
sender account is required. This can be given via configuration

.. code-block:: yaml

	bitshares:
	    exchange_account_memo_key: <insert exchange account memo key>
	
	    connection:
	        [Test|Main]:
	         keys:
	            - <insert any other required memo key, e.g. for test purposes>

or given with the addressContext argument of the 

.. code-block:: html

	[POST] /api/transactions

post request. If the sender is the exchange account and no addressContext is given, its memo key
is loaded from the configuration file entry exchange_account_memo_key, otherwise its expected to be in the connection.keys list. 

Sign service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The sign services sole purpose is to create new addresses and to sign transaction.

.. code-block:: bash

	$ python3 cli.py sign_service
  
To sign the transaction it requires the active key of the sender account. 
This can be given via configuration

.. code-block:: yaml

	bitshares:
        exchange_account_active_key: <insert active key of exchange account here>
	    keep_keys_private: [True|False]
	    connection:
	        [Test|Main]:
	         keys:
	            - <insert any other required active key, e.g. for test purposes>

or given with the privateKeys argument of the 

.. code-block:: html

	[POST] /api/sign

post call. If the sender is the exchange account and no privateKeys is given or set to the 
keyword "keep_keys_private", its active key is loaded from the configuration file entry 
bitshares.exchange_account_active_key, otherwise its expected to be in the connection.keys list.

The configuration flag bitshares.keep_keys_private controls whether any keys are returned with the

.. code-block:: html

	[POST] /api/wallets
 
post call. If the flag is set, no keys are returned (privateKey is set to "keep_keys_private"), otherwise
the response contains the active and memo key of the exchange account, additionally to a new publicAddress

.. code-block:: yaml

  privateKey: bitshares.exchange_account_active_key
  addressContext: bitshares.exchange_account_memo_key


Blockchain monitor
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The blockchain monitor monitors the blockchain for transactions involving the exchange account. Is is started
like

.. code-block:: bash

	$ python3 cli.py blockchain_monitor
	
To be able to read the memo messages of all those transfers it requires the memo key of the exchange account, 
which needs to be given in the configuration

.. code-block:: yaml

	bitshares:
	    exchange_account_memo_key: <insert exchange account memo key>

Blockchain monitor service
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The blockchain monitor service simply provides a WSGI isalive call for administration purposes and is started
like shown below

.. code-block:: bash

	$ python3 cli.py blockchain_monitor_service
