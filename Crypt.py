from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from ipfshttpclient import client
import io
import base64
from cryptography.hazmat.primitives import serialization
from web3 import Web3
ipfs_node = "/ip4/127.0.0.1/tcp/5001/http"
ipfs_client = client.Client(ipfs_node)

ganache_url = "HTTP://127.0.0.1:7545"
provider = Web3.HTTPProvider(ganache_url)
web3 = Web3(provider)

contract_abi = [
	{
		"inputs": [],
		"stateMutability": "nonpayable",
		"type": "constructor"
	},
	{
		"inputs": [],
		"name": "getNumber",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "idR",
				"type": "uint256"
			}
		],
		"name": "getString",
		"outputs": [
			{
				"internalType": "string",
				"name": "",
				"type": "string"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "getStringCount",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "string",
				"name": "newString",
				"type": "string"
			}
		],
		"name": "setString",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "storedNumber",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"name": "strings",
		"outputs": [
			{
				"internalType": "string",
				"name": "",
				"type": "string"
			}
		],
		"stateMutability": "view",
		"type": "function"
	}
]

contract_address = Web3.to_checksum_address("0x334a3caa70f35470a9423aeb34bf272aa7c834b1")
contract = web3.eth.contract(address=contract_address, abi=contract_abi)

class Crypt:
    def __init__(self):
      pass
      
    
    def generate_key_pair(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        return private_key, public_key

    def encrypt_with_public_key(self, public_key, plaintext):
        ciphertext = public_key.encrypt(
            plaintext.encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return ciphertext


    def decrypt_with_private_key(self, private_key, ciphertext):
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext

    def upload_pdf(self, pdf_file_path):
        with open(pdf_file_path, "rb") as file:
            file_data = file.read()
        file_stream = io.BytesIO(file_data)
        file_added = ipfs_client.add(file_stream, raw_leaves=True)
        ipfs_hash = file_added["Hash"]
        return ipfs_hash
      
    def store_string(self,hash_str):
      store_file_txn = contract.functions.setString(hash_str).transact({'from': web3.eth.accounts[0]})
      web3.eth.wait_for_transaction_receipt(store_file_txn)
      
    def getId(self):
      id = contract.functions.getNumber().call()
      return id
    
    def getString(self,id):
      return contract.functions.getString(id).call()
    
    def ExtractPdfData(self,deHash):
      return ipfs_client.cat(deHash)
