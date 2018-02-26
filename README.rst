Short ReadMe
============

Bexi is written in python and enables the integration of BitShares into an external exchange. The basic idea is that
the external exchange will have one BitShares account to consolidate the funds that it holds for  
the customers. Deposits and withdrawals into and from said account is tracked and the customer balance
calculated.

Nevertheless, this module is not meant to be an accounting platform for the external exchange, it is merely
the technical realization of the integration.

Supported exchanges
-------------------

This software was motivated and constructed for the implementation of the Lykke exchange. Thanks to Lykke
it is available as open source (for licensing information please see LICENSE.rst file).
If you operate your own exchange and wish to integrate BitShares, feel free to contact info@blockchainprojectsbv.com.

This library was implemented according to 
	
	https://streams.lykke.com/Project/ProjectDetails/bitshares-blockchain-integration-api
	https://docs.google.com/document/d/1KVd-2tg-Ze5-b3kFYh1GUdGn9jvoo7HFO3wH_knpd3U/edit


Who do I talk to?
-----------------

info@blockchainprojectsbv.com

Installation
----------
Install environment
	
.. code-block:: bash

	$ apt-get install -y python3 python3-pip

Install virtual environment and setup 

.. code-block:: bash

	$ pip3 install virtualenv
	$ virtualenv env 
	$ source env/bin/activate
	$ pip install -r requirements.txt

Run all tests (tox installation required)

.. code-block:: bash

	$ pip install -r requirements-test.txt
	$ tox

Build documentation:

.. code-block:: bash

	$ make docs

Quick Guide
----------
Fill in the operation storage details, 
as well as the BitShares exchange account and connection
details in the config yaml files.
The manage_service and blockchain_monitor require the memo key of the 
exchange account, whereas the sign_service requires only the active key.
The active key is what you normally see as the private key, since it allows
to move funds, whereas the memo key only allows reading the memo message of
transfers. 

Then initiate the blockchain monitor

.. code-block:: bash

	$ python3 cli.py blockchain_monitor
  
Start the sign service

.. code-block:: bash

	$ python3 cli.py sign_service
  
and the manage service

.. code-block:: bash

	$ python3 cli.py manage_service