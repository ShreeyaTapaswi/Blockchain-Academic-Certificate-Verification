"""Unit tests - 31474 - Shreeya Tapaswi"""
import unittest

from blockchain import Blockchain, Institution, Transaction, certificate_hash


def make():
    chain = Blockchain()
    inst = Institution("PICT")
    chain.register_institution(inst)
    return chain, inst


def issue_tx(inst, h, kind="ISSUE"):
    return Transaction(kind, h, inst.public_key_hex, inst.sign(f"{kind}:{h}"))


class CertTests(unittest.TestCase):
    def setUp(self):
        self.chain, self.inst = make()
        self.h = certificate_hash("1", "A", "BTech", "A", "2026-01-01", "PICT")

    def test_issue_and_verify(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        self.chain.mine_pending()
        self.assertTrue(self.chain.verify_certificate(self.h)["valid"])

    def test_unknown_certificate_invalid(self):
        self.assertFalse(self.chain.verify_certificate("abc")["valid"])

    def test_tampered_content_invalid(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        self.chain.mine_pending()
        other = certificate_hash("1", "A", "BTech", "A+", "2026-01-01", "PICT")
        self.assertFalse(self.chain.verify_certificate(other)["valid"])

    def test_unauthorised_issuer_rejected(self):
        with self.assertRaises(PermissionError):
            self.chain.add_transaction(issue_tx(Institution("Fake"), self.h))

    def test_bad_signature_rejected(self):
        tx = issue_tx(self.inst, self.h)
        tx.signature = "00" * 64
        with self.assertRaises(ValueError):
            self.chain.add_transaction(tx)

    def test_duplicate_issue_rejected(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        self.chain.mine_pending()
        with self.assertRaises(ValueError):
            self.chain.add_transaction(issue_tx(self.inst, self.h))

    def test_revocation(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        self.chain.mine_pending()
        self.chain.add_transaction(issue_tx(self.inst, self.h, "REVOKE"))
        self.chain.mine_pending()
        self.assertFalse(self.chain.verify_certificate(self.h)["valid"])

    def test_other_institution_cannot_revoke(self):
        other = Institution("Other")
        self.chain.register_institution(other)
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        self.chain.mine_pending()
        with self.assertRaises(PermissionError):
            self.chain.add_transaction(issue_tx(other, self.h, "REVOKE"))

    def test_chain_tamper_detected(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        self.chain.mine_pending()
        self.assertTrue(self.chain.is_chain_valid())
        self.chain.chain[1].transactions[0]["cert_hash"] = "f" * 64
        self.assertFalse(self.chain.is_chain_valid())


if __name__ == "__main__":
    unittest.main()
