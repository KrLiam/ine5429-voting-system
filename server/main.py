from dataclasses import dataclass, field
import secrets
from typing import Any
import phe
import time
from flask import Flask, request, send_from_directory, jsonify


def generate_keys():
    return phe.generate_paillier_keypair(n_length=2048)


Vote = list[phe.EncryptedNumber]

class BulletinBoard:
    tokens: dict[str, bool]
    votes: list[Vote]

    def __init__(self, ntokens: int) -> None:
        self.tokens = {}
        self.votes = []

        # generate tokens
        for _ in range(ntokens):
            self.tokens[secrets.token_hex(32)] = False

    def insert_vote(self, vote: Vote):
        i = 0 # isso deve ser gerado aleatoriamente
        self.votes.insert(i, vote)

    def mark_token(self, token: str):
        if token not in self.tokens:
            return
        self.tokens[token] = True
    
    def dump_tokens(self, path: str):
        with open(path, "wt") as f:
            f.write("\n".join(key for key in self.tokens))


class Authority:
    public_key: phe.PaillierPublicKey
    private_key: phe.PaillierPrivateKey

    def __init__(self):
        self.public_key, self.private_key = generate_keys()

    def get_public_key(self) -> phe.PaillierPublicKey:
        return self.public_key
    
    def reveal(self, result: list[phe.EncryptedNumber]) -> list[int]:
        return [self.private_key.decrypt(v) for v in result]


class Server:
    authority: Authority
    public_key: phe.PaillierPublicKey
    about: str
    start_time: float
    duration: float
    candidates: list[str]
    tokens: dict[str, bool]

    bb: BulletinBoard

    def __init__(
            self,
            authority: Authority,
            candidates: list[str],
            ntokens: int,
            duration: int = 5,
            about: str = "",
            token_dump_path: str | None = None,
        ):
        self.authority = authority
        self.public_key = authority.get_public_key()
        self.start_time = time.time()
        self.duration = 60 * duration # 1 hora
        self.candidates = candidates
        self.about = about

        self.bb = BulletinBoard(ntokens)

        if token_dump_path is not None:
            self.bb.dump_tokens(token_dump_path)

        self.app = Flask(
            __name__,
            static_folder="../public",
            static_url_path=""
        )

        self.register_routes()
    
    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    def over(self) -> bool:
        return time.time() >= self.end_time
    
    def validate_token(self, token: str) -> bool:        
        return token in self.bb.tokens and not self.bb.tokens[token]
    
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

        @self.app.route("/election")
        def get_election():
            return jsonify({
                "key": {"n": str(self.public_key.n), "g": str(self.public_key.g)},
                "end_time": self.end_time,
                "about": self.about,
                "candidates": self.candidates,
            })
                
        @self.app.route("/validate-token")
        def validate_token():
            token = request.args.get("token") or ""
            return jsonify({"valid": self.validate_token(token) })
        
        @self.app.route("/vote", methods=["POST"])
        def vote():
            if self.over():
                return jsonify({
                    "ok": False,
                    "message": "Eleição encerrada."
                })
        
            data = request.get_json()
            token = data.get("token")
            values = data.get("value")

            if not self.validate_token(token):
                return jsonify({
                    "ok": False,
                    "message": "Token inválido."
                })

            vote = self.convert_vote(values)

            self.bb.mark_token(token)
            self.bb.insert_vote(vote)

            return jsonify({
                "ok": True,
                "message": "Voto registrado."
            })

        @self.app.route("/result")
        def get_result():
            if not self.over():
                return jsonify({"ok": False})
            
            vote_sum = [0] * len(self.candidates)

            if not len(self.bb.votes):
                return vote_sum

            for i, _ in enumerate(self.candidates):
                s = self.bb.votes[0][i]
                for vote in self.bb.votes[1:]:
                    s = s + vote[i]
                vote_sum[i] = s

            result = self.authority.reveal(vote_sum)
            
            return jsonify({
                "ok": True,
                "result": result, 
            })

    def run(self, host="0.0.0.0", port=5000):
        self.app.run(host=host, port=port)


if __name__ == "__main__":
    authority = Authority()

    server = Server(
        authority=authority,
        about="Quem você vota para presidente?",
        candidates=["Jean", "Thais"],
        duration=30,
        ntokens=43,
        token_dump_path="tokens.txt"
    )
    server.run()
