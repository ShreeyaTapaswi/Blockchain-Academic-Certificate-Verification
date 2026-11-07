"""[31474 - Shreeya Tapaswi]
Core blockchain for the Academic Certificate Verification System.

A permissioned blockchain:
  * every certificate is reduced to a SHA-256 fingerprint (no personal data on-chain)
  * institutions sign ISSUE / REVOKE transactions with Ed25519 keys
  * transactions wait in a pending pool until a block is mined
  * each block stores a Merkle root of its transactions and is sealed with proof of work
  * blocks are linked by hash, so any edit to history is detectable
"""
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

DEFAULT_DIFFICULTY = 3  # leading zeros required in a block hash


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def certificate_hash(student_id: str, name: str, course: str,
                     grade: str, issue_date: str, institution: str) -> str:
    """Deterministic fingerprint of a certificate's contents."""
    payload = json.dumps(
        {"student_id": student_id, "name": name, "course": course,
         "grade": grade, "issue_date": issue_date, "institution": institution},
        sort_keys=True)
    return sha256(payload)


# ---------------------------------------------------------------- Merkle tree
def tx_hash(tx: dict) -> str:
    return sha256(json.dumps(tx, sort_keys=True))


def merkle_levels(leaves: List[str]) -> List[List[str]]:
    """Return every level of the Merkle tree, from the leaves up to the root.
    An odd level is padded by repeating its last node."""
    if not leaves:
        return [[sha256("")]]
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        if len(cur) % 2:
            cur.append(cur[-1])
        levels.append([sha256(cur[i] + cur[i + 1]) for i in range(0, len(cur), 2)])
    return levels


def merkle_root(leaves: List[str]) -> str:
    return merkle_levels(leaves)[-1][0]


# ------------------------------------------------------------- keys / signing
class Institution:
    """An institution holding an Ed25519 key pair."""

    def __init__(self, name: str, private_hex: Optional[str] = None):
        self.name = name
        self._private = (ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_hex))
                         if private_hex else ed25519.Ed25519PrivateKey.generate())
        self.public_key_hex = self._private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def private_hex(self) -> str:
        return self._private.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption()).hex()

    def sign(self, message: str) -> str:
        return self._private.sign(message.encode()).hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), message.encode())
        return True
    except (InvalidSignature, ValueError):
        return False


# ------------------------------------------------------------ data structures
@dataclass
class Transaction:
    kind: str            # "ISSUE" or "REVOKE"
    cert_hash: str
    issuer: str          # institution public key (hex)
    signature: str
    timestamp: float = field(default_factory=time.time)

    def signed_message(self) -> str:
        return f"{self.kind}:{self.cert_hash}"

    def to_dict(self):
        return asdict(self)


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[dict]
    previous_hash: str
    nonce: int = 0
    hash: str = ""
    merkle_root: str = ""
    difficulty: int = DEFAULT_DIFFICULTY

    def compute_merkle_root(self) -> str:
        return merkle_root([tx_hash(t) for t in self.transactions])

    def compute_hash(self) -> str:
        body = json.dumps({"index": self.index, "timestamp": self.timestamp,
                           "merkle_root": self.merkle_root,
                           "previous_hash": self.previous_hash,
                           "nonce": self.nonce, "difficulty": self.difficulty},
                          sort_keys=True)
        return sha256(body)

    def mine(self):
        """Proof of work: find a nonce so the hash starts with `difficulty` zeros."""
        self.merkle_root = self.compute_merkle_root()
        prefix = "0" * self.difficulty
        self.nonce = 0
        while True:
            self.hash = self.compute_hash()
            if self.hash.startswith(prefix):
                return
            self.nonce += 1


# ----------------------------------------------------------------- blockchain
class Blockchain:
    def __init__(self, difficulty: int = DEFAULT_DIFFICULTY, genesis: bool = True):
        self.difficulty = difficulty
        self.chain: List[Block] = []
        self.pending: List[Transaction] = []
        self.authorised_issuers = {}  # public key hex -> institution name
        if genesis:
            g = Block(0, time.time(), [], "0" * 64, difficulty=difficulty)
            g.mine()
            self.chain.append(g)

    # ---- issuer registry -------------------------------------------------
    def register_institution(self, inst: Institution):
        self.authorised_issuers[inst.public_key_hex] = inst.name

    # ---- transactions ----------------------------------------------------
    def add_transaction(self, tx: Transaction) -> bool:
        if tx.issuer not in self.authorised_issuers:
            raise PermissionError("Issuer is not an authorised institution")
        if not verify_signature(tx.issuer, tx.signed_message(), tx.signature):
            raise ValueError("Invalid signature")
        status = self.find(tx.cert_hash)
        pend = [p for p in self.pending if p.cert_hash == tx.cert_hash]
        if tx.kind == "ISSUE":
            if status is not None or any(p.kind == "ISSUE" for p in pend):
                raise ValueError("Certificate already issued")
        elif tx.kind == "REVOKE":
            if status is None:
                if any(p.kind == "ISSUE" for p in pend):
                    raise ValueError("Certificate is still pending - mine the block first")
                raise ValueError("Certificate not found")
            if status["issuer"] != tx.issuer:
                raise PermissionError("Only the issuing institution can revoke")
            if status["revoked"] or any(p.kind == "REVOKE" for p in pend):
                raise ValueError("Certificate already revoked")
        else:
            raise ValueError("Unknown transaction type")
        self.pending.append(tx)
        return True

    def mine_pending(self) -> Optional[Block]:
        if not self.pending:
            return None
        block = Block(len(self.chain), time.time(),
                      [t.to_dict() for t in self.pending], self.chain[-1].hash,
                      difficulty=self.difficulty)
        block.mine()
        self.chain.append(block)
        self.pending = []
        return block

    # ---- queries ---------------------------------------------------------
    def find(self, cert_hash: str) -> Optional[dict]:
        """Ledger record for a certificate (mined transactions only), or None."""
        record = None
        for block in self.chain:
            for tx in block.transactions:
                if tx["cert_hash"] != cert_hash:
                    continue
                if tx["kind"] == "ISSUE" and record is None:
                    record = {"issuer": tx["issuer"], "signature": tx["signature"],
                              "revoked": False, "revoked_block": None,
                              "block": block.index, "timestamp": tx["timestamp"]}
                elif tx["kind"] == "REVOKE" and record:
                    record["revoked"] = True
                    record["revoked_block"] = block.index
        return record

    def is_pending(self, cert_hash: str) -> bool:
        return any(p.cert_hash == cert_hash and p.kind == "ISSUE" for p in self.pending)

    def verify_certificate(self, cert_hash: str) -> dict:
        rec = self.find(cert_hash)
        if rec is None:
            if self.is_pending(cert_hash):
                return {"valid": False, "pending": True,
                        "reason": "Issued but not yet mined into a block (pending)"}
            return {"valid": False, "reason": "Certificate not found on the ledger"}
        if rec["revoked"]:
            return {"valid": False, "reason": "Certificate has been revoked", **rec}
        return {"valid": True, "reason": "Certificate is authentic",
                "institution": self.authorised_issuers.get(rec["issuer"], "Unknown"), **rec}

    # ---- integrity -------------------------------------------------------
    def validate(self) -> List[dict]:
        """Return a list of integrity problems (empty list = chain is valid)."""
        issues = []
        for i, b in enumerate(self.chain):
            def add(kind, msg, _b=b):
                issues.append({"block": _b.index, "kind": kind, "message": msg})
            if b.merkle_root != b.compute_merkle_root():
                add("merkle", "Transactions no longer match the block's Merkle root")
            if b.hash != b.compute_hash():
                add("hash", "Stored hash does not match the recomputed block hash")
            if not b.hash.startswith("0" * b.difficulty):
                add("pow", "Hash does not satisfy the proof-of-work target")
            if i > 0 and b.previous_hash != self.chain[i - 1].hash:
                add("link", f"Link to block #{i - 1} is broken (previous hash mismatch)")
            for tx in b.transactions:
                msg = f"{tx['kind']}:{tx['cert_hash']}"
                if not verify_signature(tx["issuer"], msg, tx["signature"]):
                    add("signature", "A transaction signature is invalid")
                    break
        return issues

    def is_chain_valid(self) -> bool:
        return not self.validate()

    # ---- demo only: simulate an attacker ----------------------------------
    def tamper_block(self, index: int, smart: bool = False) -> dict:
        """Edit the first transaction of a block. A 'smart' attacker also
        recomputes the Merkle root and re-mines the block so it looks
        self-consistent - but then the link from the next block breaks."""
        if index < 1 or index >= len(self.chain) or not self.chain[index].transactions:
            raise ValueError("Choose a block that contains certificates")
        block = self.chain[index]
        tx = block.transactions[0]
        old = tx["cert_hash"]
        tx["cert_hash"] = ("f" if old[0] != "f" else "e") + old[1:]
        if smart:
            block.mine()
        return {"block": index, "old": old, "new": tx["cert_hash"], "smart": smart}

    # ---- persistence ------------------------------------------------------
    def to_dict(self) -> dict:
        return {"difficulty": self.difficulty,
                "chain": [asdict(b) for b in self.chain],
                "pending": [asdict(t) for t in self.pending],
                "issuers": dict(self.authorised_issuers)}

    @classmethod
    def from_dict(cls, d: dict) -> "Blockchain":
        bc = cls(d["difficulty"], genesis=False)
        bc.chain = [Block(**b) for b in d["chain"]]
        bc.pending = [Transaction(**t) for t in d["pending"]]
        bc.authorised_issuers = dict(d["issuers"])
        return bc
