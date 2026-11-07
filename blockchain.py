"""[31474 - Shreeya Tapaswi]
Core blockchain for the Academic Certificate Verification System.

A minimal permissioned blockchain: each block stores a list of certificate
transactions (ISSUE / REVOKE), is linked to the previous block by hash and is
sealed with a small proof-of-work. Only the certificate *hash* goes on-chain,
never personal data, so the ledger stays privacy friendly.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

DIFFICULTY = 3  # number of leading zeros required in block hash


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


class Institution:
    """An authorised issuer holding an Ed25519 key pair."""

    def __init__(self, name: str):
        self.name = name
        self._private = ed25519.Ed25519PrivateKey.generate()
        self.public_key_hex = self._private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

    def sign(self, message: str) -> str:
        return self._private.sign(message.encode()).hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), message.encode())
        return True
    except (InvalidSignature, ValueError):
        return False


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
        return self.__dict__.copy()


@dataclass
class Block:
    index: int
    timestamp: float
    transactions: List[dict]
    previous_hash: str
    nonce: int = 0
    hash: str = ""

    def compute_hash(self) -> str:
        body = json.dumps({"index": self.index, "timestamp": self.timestamp,
                           "transactions": self.transactions,
                           "previous_hash": self.previous_hash,
                           "nonce": self.nonce}, sort_keys=True)
        return sha256(body)

    def mine(self, difficulty: int = DIFFICULTY):
        prefix = "0" * difficulty
        while True:
            self.hash = self.compute_hash()
            if self.hash.startswith(prefix):
                return
            self.nonce += 1


class Blockchain:
    def __init__(self):
        self.chain: List[Block] = []
        self.pending: List[Transaction] = []
        self.authorised_issuers = {}  # public key hex -> institution name
        genesis = Block(0, time.time(), [], "0" * 64)
        genesis.mine()
        self.chain.append(genesis)

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
        if tx.kind == "ISSUE" and status is not None:
            raise ValueError("Certificate already issued")
        if tx.kind == "REVOKE":
            if status is None:
                raise ValueError("Certificate not found")
            if status["issuer"] != tx.issuer:
                raise PermissionError("Only the issuing institution can revoke")
        self.pending.append(tx)
        return True

    def mine_pending(self) -> Optional[Block]:
        if not self.pending:
            return None
        block = Block(len(self.chain), time.time(),
                      [t.to_dict() for t in self.pending], self.chain[-1].hash)
        block.mine()
        self.chain.append(block)
        self.pending = []
        return block

    # ---- queries ---------------------------------------------------------
    def find(self, cert_hash: str) -> Optional[dict]:
        """Return {'issuer', 'revoked', 'block'} for a certificate, or None."""
        record = None
        for block in self.chain:
            for tx in block.transactions:
                if tx["cert_hash"] != cert_hash:
                    continue
                if tx["kind"] == "ISSUE":
                    record = {"issuer": tx["issuer"], "revoked": False,
                              "block": block.index, "timestamp": tx["timestamp"]}
                elif tx["kind"] == "REVOKE" and record:
                    record["revoked"] = True
        return record

    def verify_certificate(self, cert_hash: str) -> dict:
        rec = self.find(cert_hash)
        if rec is None:
            return {"valid": False, "reason": "Certificate not found on the ledger"}
        if rec["revoked"]:
            return {"valid": False, "reason": "Certificate has been revoked", **rec}
        return {"valid": True, "reason": "Certificate is authentic",
                "institution": self.authorised_issuers.get(rec["issuer"], "Unknown"),
                **rec}

    def is_chain_valid(self) -> bool:
        prefix = "0" * DIFFICULTY
        for i, block in enumerate(self.chain):
            if block.hash != block.compute_hash() or not block.hash.startswith(prefix):
                return False
            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                return False
        return True
