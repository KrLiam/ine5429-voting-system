from dataclasses import dataclass, field
from typing import Any
import phe
import time
from flask import Flask, request, send_from_directory, jsonify


def generate_keys():
    return phe.generate_paillier_keypair(n_length=2048)


Vote = list[phe.EncryptedNumber]

@dataclass
class BulletinBoard:
    voters: list[int] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)

    def insert_vote(self, vote: list[phe.EncryptedNumber]):
        i = 0 # isso deve ser gerado aleatoriamente
        self.votes.insert(i, vote)

    def insert_voter(self, vote: int):
        i = 0 # isso deve ser gerado aleatoriamente
        self.voters.insert(i, vote)


@dataclass
class Contador:
    candidates: list[str]
    private_key: phe.PaillierPrivateKey
    
    def count(self, bb: BulletinBoard) -> list[int]:
        result = [0] * len(self.candidates)

        if not len(bb.votes):
            return result

        for i, _ in enumerate(self.candidates):
            s = bb.votes[0][i]
            for vote in bb.votes[1:]:
                s = s + vote[i]
            
            result[i] = self.private_key.decrypt(s)
        
        return result


class Server:
    private_key: phe.PaillierPrivateKey
    public_key: phe.PaillierPublicKey
    start_time: float
    duration: float
    candidates: list[str]

    bb: BulletinBoard

    def __init__(self, candidates: list[str]):
        pk, sk = generate_keys()
        self.public_key = pk
        self.private_key = sk
        self.start_time = time.time()
        self.duration = 60 # 1 hora
        self.candidates = candidates

        self.bb = BulletinBoard()

        self.app = Flask(
            __name__,
            static_folder="../public",
            static_url_path=""
        )

        self.register_routes()
    
    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    def validate_id(self, id: str) -> int | None:
        if not id.isdigit():
            return None
        
        parsed_id = int(id)
        if parsed_id in self.bb.voters:
            return None
        
        return parsed_id
    
    def convert_vote(self, value: list[Any]) -> list[phe.EncryptedNumber]:
        result: list[phe.EncryptedNumber] = []
        for v in value:
            if isinstance(v, str):
                v = int(v)
            result.append(phe.EncryptedNumber(self.public_key, v))
        return result

    def register_routes(self):
        @self.app.route("/")
        def serve_index():
            # serve public/index.html
            return send_from_directory("../public", "index.html")

        @self.app.route("/key")
        def get_key():
            return jsonify({"n": str(self.public_key.n), "g": str(self.public_key.g)})
        
        @self.app.route("/endtime")
        def get_endtime():
            t = self.start_time + self.duration
            return jsonify({"endtime": t})

        @self.app.route("/candidates")
        def get_candidates():
            return jsonify(self.candidates)
        
        @self.app.route("/validate-id")
        def validate_id():
            voter_id = request.args.get("id")
            voter_id = self.validate_id(voter_id) if voter_id else None
            return jsonify({"valid": voter_id is not None})
        
        @self.app.route("/vote", methods=["POST"])
        def vote():
            data = request.get_json()
            id = data.get("id")
            values = data.get("value")

            id = self.validate_id(id)
            if id is None:
                return jsonify({
                    "status": "error",
                    "message": "Este id é inválido."
                })

            print("received vote of", id, values)

            vote = self.convert_vote(values)
            self.bb.insert_voter(id)
            self.bb.insert_vote(vote)

            return jsonify({
                "status": "ok",
                "message": "Voto registrado."
            })

        @self.app.route("/result")
        def get_result():
            if not self.over():
                return jsonify({"ok": False})
            
            counter = Contador(self.candidates, self.private_key)
            result = counter.count(self.bb)
            return jsonify({
                "ok": True,
                "result": result, 
            })

    def over(self) -> bool:
        return time.time() >= self.end_time

    def run(self, host="0.0.0.0", port=5000):
        self.app.run(host=host, port=port)


if __name__ == "__main__":
    server = Server(candidates=[
        "Bolsonaro",
        "Lula"
    ])
    server.run()
