Use cases of Bexi and introduction to BitShares's key features
*********************************************************************

This documented gives an introduction behind the possibilities to implement integration of any BitShares asset into an external exchange. For that purpose we introduce the key functionalities of BitShares that are being utilized and describe two different ways to implement withdrawals and deposits.

.. contents::

Named Accounts with Authorities
=====================================

Every BitShares account is assigned a globally unique name which is selected by the user  when registering the account.. An account name is an alias to a set of dynamic account authorities. 
An authority contains a list of weighted public keys (default is only one key with weight 1) that allows the user to execute a certain functionality on the blockchain via cryptographically signed transactions. 
Those authorities are

 - Active authority
   Operating permission that allows e.g. to buy/sell and transfer assets and vote, and that allows to change the keys of active and memo permission
 - Owner authority
   Everything that active permission allows and additionally change of owner key
   
Additionally, an account has a memo key that has no authority whatsoever and is merely used for key exchange when encrypting and decrypting messages, e.g. the memo message of transfers.

The benefit of a named account with authorities is obvious. First of all, named accounts are easily remembered and communicated (same as IP addresses and DNS), and thus human-friendly. Second, 
dynamic account authorities provide more security and allow for management activities in the corporate environment via hierarchical multi-sig accounts instead of only flat, 1-level multi-sig schemes know 
from Blockchain technologies.

Transfer
=====================================

A transfer of an asset between two accounts is the main feature to realize deposit and withdrawals of an external exchange. Therefore, it will be explained in more detail below. A transfer essentially contains:

 - Sender account
 - Receiver account
 - Asset and amount to be transferred
 - Fee to be paid to the blockchain
 - Optional: Encrypted memo message that can only be read by sender or receiver


A transfer allows separation of concerns in terms of security:

 - Execution of a transfer requires the active authority
 - Reading (and decrypting) the memo message requires only the memo private key of the receiver or sender, e.g. when monitoring for deposits
 
Use cases for deposit/withdrawal
=====================================
In every case, the external exchange is required to have full control of at least one  BitShares account that will be the turning point for deposits and withdrawals. Certainly, separation for different purposes is possible (cold wallet, hot wallet, deposit only, withdrawal only ...).

There are methods on how to track deposits and withdrawals: Memo-based tracking and Account linking, both are briefly described below.

Memo tracking
------------------------
In this use case, the identification of the user is done via identifiable information within the memo message. This is the most flexible solution but it requires a more sophisticated tracking approach for deposits.

Triggering a deposit
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
User initiates a deposit on the external exchange and gets a specific memo message and target BitShares account. User then transfers the desired asset to the target BitShares account with a specific memo message. Said memo message allows unique mapping of this transfer to the user.

Triggering a withdrawal
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
User initiates a withdrawal by providing the asset name, amount and target BitShares account name. The external exchange executes the transfer to this target BitShares account.

Recognizing deposits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The external exchange needs to process all incoming transfers and decides with the memo message (after decrypting with the exchange's memo private key) which user to credit.

Advantages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

 - User can use arbitrary many accounts for deposit and withdrawal
 - User is forced to check the account on every withdrawal, reduces risk when a user's BitShares account gets compromised

Disadvantages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

 - Monitoring deposits requires knowledge of memo private key
 - User bears risk of mistyping memo message for deposits
 - User bears risk of mistyping BitShares account for withdrawals
 
Account linking
------------------------
In this use case, the user links his/her BitShares account name to the external exchange during registration. Ownership of the account must be validated. This can be done in two ways:
 
 - A BitShares signed message that proves that control over the memo key. Such a message can be created in the reference wallet
 - Transfer a dust amount of a specified asset with an encrypted memo message, which proves control over the active permission and the memo key

For example, such a message could be
Signing up at "someexchange.com" with username "sschiessl-suffix"

The uniqueness of such an external username to the BitShares account name must be ensured by the external exchange.

Triggering a deposit
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
User does not need to initiate a deposit., Every transfer to the external exchange's BitShares account from the linked BitShares account is credited to the user. Optional a specific memo message can be enclosed.

Triggering a withdrawal
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
User initiates a withdrawal by providing the asset name and amount to be withdrawn. Optional a memo message can be given by the user / defined by the external exchange. The external exchange then executes the transfer to the user's linked BitShares account.

Recognizing deposits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
All transfers from the user's linked BitShares account to the external exchange's BitShares account are credited to the user.

Advantages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

 - Deposits and withdrawals can easily be mapped to the user, the only risk of mistyping is when registering
 - Monitoring deposits does not require knowledge of any keys

Disadvantage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

 - User can only perform deposits and withdrawals using the predefined BitShares account
 - Proof of ownership of the linked BitShares account must be ensured, e.g. signed message can't be older than 10 minutes, must contain user specific text, etc.
 - User can forget which account is linked, lose control over said account or simply transfer ownership


Independent of the chosen method, an exchange needs to consider and implement action points for the following failure scenarios:
 - A deposit cannot be assigned to a user in the exchanges' internal database (either by a missing or use of an unknown memo, or by sending from an unknown account)

APIs
=========
As with other blockchain systems, there is no centralized service that lets you access private API calls after successful authentication. Instead, a wallet API offers private functionalities (such as transfers, etc) via locally signed transactions. 
All other public readable information can be queried via a public blockchain API. Hence, APIs are separated into two general categories, namely

 - Blockchain API which is used to query blockchain data (account, assets, trading history, etc.) and is offered by the witness_node application.
 - Wallet API which has your private keys loaded and is required when interacting with the blockchain with new transactions. The purpose of a wallet is to safely store the private keys to an account and sign transactions according to the user's inputs. 
    Developers have the choice between hooking up with the cli_wallet API (C++), use the wallet functionality of pybitshares (python) or bitsharesjs (Javascript).

As an exchange, it is highly recommend to run and maintain a local blockchain (API) node for a trusted setup.

Monitoring the Blockchain
===========================
When monitoring a Blockchain, the most important question to answer is which block is considered final. In case of Bitcoin, most businesses consider 6 confirmations (e.g. a block that is buried in the blockchain by at least 5 more blocks) final. 
In the case of Graphene, we have a very specific definition of finality. Ultimately, the so called irreversible block and all blocks that happened before that are considered final. Fortunately, the irreversible block can be obtained from the API directly 
as it is well known by the software. There even is a so called delayed node that connects to a regular node and is only aware of blocks that are final.

Two options exist for monitoring the BitShares Blockchain for new events that affect the exchange's business (e.g. deposits):
 - Process each block individually
 - Register for notifications on the backend API
