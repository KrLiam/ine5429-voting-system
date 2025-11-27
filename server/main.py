from pathlib import Path
from datetime import datetime
import secrets
from typing import Any
import phe
import time
from random import SystemRandom
from flask import Flask, json, request, send_from_directory, jsonify
from waitress import serve


BULLETIN_BOARD_PATH = "data/bulletin_board.json"
AUTHORITY_PATH = "data/authority.json"

def generate_keys():
    return phe.generate_paillier_keypair(n_length=2048)


Vote = list[phe.EncryptedNumber]

def convert_vote(value: list[Any], public_key: phe.PaillierPublicKey) -> Vote:
    result: list[phe.EncryptedNumber] = []
    for v in value:
        if isinstance(v, str):
            v = int(v)
        result.append(phe.EncryptedNumber(public_key, v))
    return result


class BulletinBoard:
    start_time: int
    duration: int
    tokens: dict[str, bool]
    votes: list[Vote]

    gen: SystemRandom

    def __init__(
        self,
        ntokens: int,
        start_time: int,
        duration: int,
        tokens: dict[str, bool] | None = None,
        votes: list[Vote] | None = None,

    ) -> None:
        self.start_time = start_time
        self.duration = duration
        self.tokens = tokens or {}
        self.votes = votes or []

        self.gen = SystemRandom()

        if not self.tokens:
            self.generate_tokens(ntokens)

    @classmethod
    def load_or_default(
        cls,
        path: str,
        public_key: phe.PaillierPublicKey,
        ntokens: int,
        duration: int,
    ) -> "BulletinBoard":
        if Path(path).exists():
            obj = json.load(open(path, "rt"))

            start_time = obj.get("start_time", time.time())
            duration = obj.get("duration", duration)

            return BulletinBoard(
                start_time=start_time,
                duration=duration,
                ntokens=len(obj.get("tokens", {})),
                tokens=obj.get("tokens", {}),
                votes=[convert_vote(v, public_key) for v in obj.get("votes", [])]
            )
        return BulletinBoard(ntokens, time.time(), duration)

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration
    
    def generate_tokens(self, ntokens: int):
        for _ in range(ntokens):
            self.tokens[secrets.token_hex(32)] = False
        self.dump_data()

    def insert_vote(self, vote: Vote):
        i = self.gen.randrange(0, max(1, len(self.votes)))
        self.votes.insert(i, vote)
        self.dump_data()

    def mark_token(self, token: str):
        if token not in self.tokens:
            return
        self.tokens[token] = True
        self.dump_data()
    
    def dump_tokens(self, path: str):
        with open(path, "wt") as f:
            f.write("\n".join(key for key in self.tokens))
    
    def dump_data(self):
        obj = {
            "start_time": self.start_time,
            "duration": self.duration,
            "tokens": self.tokens,
            "votes": [
                [part.ciphertext() for part in vote]
                for vote in self.votes
            ],
        }
        json.dump(obj, open(BULLETIN_BOARD_PATH, "wt"), indent=4)


class Authority:
    public_key: phe.PaillierPublicKey
    private_key: phe.PaillierPrivateKey

    def __init__(self, keys: tuple[phe.PaillierPublicKey, phe.PaillierPrivateKey] | None = None):
        keys = keys or generate_keys()
        self.public_key, self.private_key = keys
    
    @classmethod
    def load_or_default(self, path: str) -> "Authority":
        if Path(path).exists():
            obj = json.load(open(path, "rt"))

            public = phe.PaillierPublicKey(obj["n"])
            private = phe.PaillierPrivateKey(public, obj["p"], obj["q"])
            return Authority((public, private))
        
        return Authority()

    def get_public_key(self) -> phe.PaillierPublicKey:
        return self.public_key
    
    def reveal(self, result: list[phe.EncryptedNumber]) -> list[int]:
        return [self.private_key.decrypt(v) for v in result]

    def save(self, path: str):
        json.dump(
            {
                "n": self.public_key.n,
                "p": self.private_key.p,
                "q": self.private_key.q,
            },
            open(path, "wt"),
            indent=4
        )


class Server:
    authority: Authority
    public_key: phe.PaillierPublicKey
    about: str
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
        self.candidates = candidates
        self.about = about

        self.bb = BulletinBoard.load_or_default(
            BULLETIN_BOARD_PATH,
            self.public_key,
            ntokens,
            duration,
        )

        if token_dump_path is not None:
            self.bb.dump_tokens(token_dump_path)

        self.app = Flask(
            __name__,
            static_folder="../public",
            static_url_path=""
        )

        self.register_routes()

    def over(self) -> bool:
        return time.time() >= self.bb.end_time
    
    def validate_token(self, token: str) -> bool:        
        return token in self.bb.tokens and not self.bb.tokens[token]
    
    def register_routes(self):
        @self.app.route("/")
        def serve_index():
            # serve public/index.html
            return send_from_directory("../public", "index.html")

        @self.app.route("/election")
        def get_election():
            return jsonify({
                "key": {"n": str(self.public_key.n), "g": str(self.public_key.g)},
                "end_time": self.bb.end_time,
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

            vote = convert_vote(values, self.public_key)

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
        serve(self.app, host=host, port=port)


def seconds_until(target_str: str) -> int:
    """
    Retorna o número de segundos até uma data no formato YYYY-MM-DD HH-MM
    """
    # Parse the custom format
    target = datetime.strptime(target_str, "%Y-%m-%d %H:%M")
    now = datetime.now()

    # Compute difference
    diff = target - now
    return int(diff.total_seconds())


if __name__ == "__main__":
    Path("data").mkdir(exist_ok=True)

    authority = Authority.load_or_default(AUTHORITY_PATH)
    authority.save(AUTHORITY_PATH)

    server = Server(
        authority=authority,
        about="Quem você vota para presidente?",
        candidates=["Jean", "Thais"],
        duration=seconds_until("2025-11-28 00:00"),
        ntokens=43,
        token_dump_path="data/tokens.txt"
        )
    server.run()
