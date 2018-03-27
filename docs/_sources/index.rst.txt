.. BEXI - BitShares Exchange Integration documentation master file, created by
   sphinx-quickstart on Mon Jan 22 16:05:15 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to BEXI - BitShares Exchange Integration's documentation!
=================================================================

BitShares is a **blockchain-based autonomous company** (i.e. a DAC) that
offers decentralized exchanging as well as sophisticated financial
instruments as *products*.

It is based on *Graphene* (tm), a blockchain technology stack (i.e.
software) that allows for fast transactions and scalable blockchain
solution. In case of BitShares, it comes with decentralized trading of
assets as well as customized on-chain smart contracts.

About this Library
------------------------

The purpose of *bexi* is to facilitate the integration of BitShares assets
into another exchange. It contains

* a BitShares block monitor that listens to relevant transfers and stores them internally
* a BitShares transaction signing service that can be operated offline
* a manage service for basic configuration, customer balance handling and building and broadcasting BitShares transactions  

For a more detailed introduction to use cases of Bexi and the utilized key features of 
BitShares from the external exchange's point of view, please visit

.. toctree::
   :maxdepth: 1

   integration

This library was created for the integration of BitShares into the Lykke exchange
and is, thanks to Lykke, available freely as open source.

Installation and quick guide are located within the readme. 

.. toctree::
   :maxdepth: 1

   readme 

.. toctree::
   :maxdepth: 1

   license

A more detailed description hwo to configure the services can be found here

.. toctree::
   :maxdepth: 1

   configuration 

Package overview
================

.. toctree::
   :maxdepth: 3

   bexi
   
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
