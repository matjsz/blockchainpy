import hashlib, json, requests
from time import time
from uuid import uuid4
from textwrap import dedent
from flask import Flask, jsonify, request
from urllib.parse import urlparse

# block = {
#     'index': 1,
#     'timestamp': 1506057125.900785,
#     'transactions': [
#         {
#             'sender': "8527147fe1f5426f9dd545de4b27ee00",
#             'recipient': "a77f5cdfa2934df3954a5c7c7da5df1f",
#             'amount': 5,
#         }
#     ],
#     'proof': 324984774000,
#     'previous_hash': "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
# }

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        # O bloco genesis
        self.newBlock(previous_hash=1, proof=100)

    def newBlock(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1])
        }

        self.current_transactions = [] # Reseta a lista de transações
        self.chain.append(block) # Adiciona o bloco à cadeia de blocos

        return block

    def newTransaction(self, sender, recipient, amount):
        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount
        }) # Adiciona transação ao bloco

        return self.lastBlock['index'] + 1 # Retorna o index do bloco da transação

    @staticmethod
    def hash(block):
        blockString = json.dumps(block, sort_keys=True).encode() # O dicionário é ordenado pelas chaves para previnir hashes inconsistentes
        return hashlib.sha256(blockString).hexdigest() # Transforma em hash e depois transforma em string

    def proofOfWork(self, last_proof): # Gera o PoW do bloco
        # Algoritmo:
        # - Encontre um número p' em que seu hash com a solução do bloco anterior seja um hash que termina em [n] [ny]s.

        proof = 0
        while self.validProof(last_proof, proof) is False:
            proof += 1

        return proof

    @staticmethod
    def validProof(last_proof, proof): # Valida a PoW
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

    def registerNode(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def validChain(self, chain):
        lastBlock = chain[0]
        currentIndex = 1

        while currentIndex < len(chain):
            block = chain[currentIndex]
            print(f'{lastBlock}')
            print(f'{block}')
            print(f'\n-----------\n')

            # Checa se o hash do bloco está correto
            if block['previous_hash'] != self.hash(lastBlock):
                return False
            
            # Checa se a PoW está correta
            if not self.validProof(lastBlock['proof'], block['proof']):
                return False
            
            last_block = block
            currentIndex += 1

        return True

    def resolveConflicts(self):
        # Essa função se baseia no Algoritmo do Consenso, o qual resolve conflitos nos Nodes ao trocar a cadeia atual pela mais longa na rede.

        neighbours = self.nodes
        newChain = None
        maxLength = len(self.chain)

        for node in neighbours:
            response = requests.get(f"http://{node}/chain")

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Checa se o tamanho da cadeia é maior e checa se a cadeia é válida
                if length > maxLength and self.validChain(chain):
                    maxLength = length
                    newChain = chain

        # Troca a cadeia se uma nova for descoberta
        if newChain:
            self.chain = newChain
            return True
        
        return False

    @property
    def lastBlock(self):
        return self.chain[-1]

# Node
app = Flask(__name__)

# Gera um endereço único para esse Node (aleatório)
nodeId = str(uuid4()).replace('-', '')

# Instancia a Blockchain
blockchain = Blockchain()

# Criando os endpoints da API

@app.route('/mine', methods=['GET'])
def mine():
    # To-do
    # - Calcular o PoW
    # - Dar a recompensa ao minerador, adicionando uma transação que garante 1 moeda
    # - Criar um novo bloco, adicionando-o à cadeia de blocos / blockchain

    # Calclar o PoW
    lastBlock = blockchain.lastBlock
    lastProof = lastBlock['proof']
    proof = blockchain.proofOfWork(lastProof)

    # Dar a recompensa ao minerador, adicionando uma transação que garante 1 moeda; O 'sender' é 0 para indicar que esse Node minerou uma nova moeda
    blockchain.newTransaction(
        sender = "0",
        recipient = nodeId,
        amount = 1
    )

    # Criar um novo bloco, adicionando-o à cadeia de blocos / blockchain
    previousHash = blockchain.hash(lastBlock)
    block = blockchain.newBlock(proof, previousHash)

    # Resposta do endpoint da API
    response = {
        'message': "Novo bloco criado",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash']
    }
    
    return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def newTranscation():
    values = request.get_json()

    # Checa se todos os valores foram satisfeitos
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Valores faltando', 400
    
    # Cria a transação
    index = blockchain.newTransaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'A transação vai ser adicionada ao bloco {index}'} # Mensagem de resposta do endpoint
    return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def fullChain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def registerNodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Erro: É necessário que uma lista válida de Nodes seja passada", 400
    
    for node in nodes:
        blockchain.registerNode(node)

    response = {
        'message': 'Novos Nodes foram adicionados',
        'total_nodes': list(blockchain.nodes)
    }
    return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolveConflicts()

    if replaced:
        response = {
            'message': 'A cadeia foi trocada',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'A cadeia permanece a mesma',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

# Rodando o Node
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)