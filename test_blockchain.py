"""Unit tests - 31474 - Shreeya Tapaswi"""
import unittest

from blockchain import (Blockchain, Institution, Transaction, certificate_hash,
                        merkle_levels, merkle_root, sha256)


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

    def _issue_and_mine(self, h=None):
        self.chain.add_transaction(issue_tx(self.inst, h or self.h))
        return self.chain.mine_pending()

    def test_issue_and_verify(self):
        self._issue_and_mine()
        self.assertTrue(self.chain.verify_certificate(self.h)["valid"])

    def test_unknown_certificate_invalid(self):
        self.assertFalse(self.chain.verify_certificate("abc")["valid"])

    def test_tampered_content_invalid(self):
        self._issue_and_mine()
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
        self._issue_and_mine()
        with self.assertRaises(ValueError):
            self.chain.add_transaction(issue_tx(self.inst, self.h))

    def test_duplicate_in_pending_pool_rejected(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        with self.assertRaises(ValueError):
            self.chain.add_transaction(issue_tx(self.inst, self.h))

    def test_pending_is_not_valid_until_mined(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        res = self.chain.verify_certificate(self.h)
        self.assertFalse(res["valid"])
        self.assertTrue(res.get("pending"))
        self.chain.mine_pending()
        self.assertTrue(self.chain.verify_certificate(self.h)["valid"])

    def test_cannot_revoke_pending_certificate(self):
        self.chain.add_transaction(issue_tx(self.inst, self.h))
        with self.assertRaises(ValueError):
            self.chain.add_transaction(issue_tx(self.inst, self.h, "REVOKE"))

    def test_revocation(self):
        self._issue_and_mine()
        self.chain.add_transaction(issue_tx(self.inst, self.h, "REVOKE"))
        self.chain.mine_pending()
        self.assertFalse(self.chain.verify_certificate(self.h)["valid"])

    def test_double_revoke_rejected(self):
        self._issue_and_mine()
        self.chain.add_transaction(issue_tx(self.inst, self.h, "REVOKE"))
        self.chain.mine_pending()
        with self.assertRaises(ValueError):
            self.chain.add_transaction(issue_tx(self.inst, self.h, "REVOKE"))

    def test_other_institution_cannot_revoke(self):
        other = Institution("Other")
        self.chain.register_institution(other)
        self._issue_and_mine()
        with self.assertRaises(PermissionError):
            self.chain.add_transaction(issue_tx(other, self.h, "REVOKE"))

    def test_chain_tamper_detected(self):
        self._issue_and_mine()
        self.assertTrue(self.chain.is_chain_valid())
        self.chain.chain[1].transactions[0]["cert_hash"] = "f" * 64
        self.assertFalse(self.chain.is_chain_valid())


class LedgerFeatureTests(unittest.TestCase):
    def setUp(self):
        self.chain, self.inst = make()
        self.hashes = [certificate_hash(str(i), "S", "BTech", "A", "2026-01-01", "PICT")
                       for i in range(3)]
        for h in self.hashes:
            self.chain.add_transaction(issue_tx(self.inst, h))
        self.chain.mine_pending()
        self.chain.add_transaction(issue_tx(self.inst, certificate_hash("9", "Z", "BTech", "A", "2026-01-01", "PICT")))
        self.chain.mine_pending()

    def test_merkle_root_stored_and_changes_with_content(self):
        block = self.chain.chain[1]
        self.assertEqual(block.merkle_root, block.compute_merkle_root())
        self.assertEqual(len(block.transactions), 3)
        before = block.compute_merkle_root()
        block.transactions[0]["kind"] = "REVOKE"
        self.assertNotEqual(before, block.compute_merkle_root())

    def test_merkle_levels_shape(self):
        levels = merkle_levels(["a", "b", "c"])
        self.assertEqual([len(l) for l in levels], [4, 2, 1])  # odd level padded
        self.assertEqual(merkle_root(["a", "b"]), sha256("a" + "b"))

    def test_naive_tamper_detected_by_merkle_root(self):
        self.chain.tamper_block(1, smart=False)
        kinds = {i["kind"] for i in self.chain.validate() if i["block"] == 1}
        self.assertIn("merkle", kinds)

    def test_smart_tamper_detected_by_broken_link(self):
        self.chain.tamper_block(1, smart=True)
        issues = self.chain.validate()
        # block 1 now looks self-consistent, but block 2 no longer links to it
        self.assertFalse([i for i in issues if i["block"] == 1 and i["kind"] in ("merkle", "hash", "pow")])
        self.assertTrue([i for i in issues if i["block"] == 2 and i["kind"] == "link"])

    def test_smart_tamper_of_last_block_caught_by_signature(self):
        self.chain.tamper_block(2, smart=True)
        self.assertTrue([i for i in self.chain.validate() if i["kind"] == "signature"])

    def test_serialisation_roundtrip(self):
        self.chain.add_transaction(issue_tx(self.inst, certificate_hash("77", "Q", "BTech", "A", "2026-01-01", "PICT")))
        copy = Blockchain.from_dict(self.chain.to_dict())
        self.assertTrue(copy.is_chain_valid())
        self.assertEqual(len(copy.chain), len(self.chain.chain))
        self.assertEqual(len(copy.pending), 1)
        self.assertEqual(copy.chain[-1].hash, self.chain.chain[-1].hash)

    def test_key_roundtrip(self):
        again = Institution("PICT", self.inst.private_hex())
        self.assertEqual(again.public_key_hex, self.inst.public_key_hex)

    def test_difficulty_respected(self):
        self.chain.difficulty = 1
        self.chain.add_transaction(issue_tx(self.inst, certificate_hash("55", "R", "BTech", "A", "2026-01-01", "PICT")))
        block = self.chain.mine_pending()
        self.assertEqual(block.difficulty, 1)
        self.assertTrue(block.hash.startswith("0"))
        self.assertTrue(self.chain.is_chain_valid())


if __name__ == "__main__":
    unittest.main()
