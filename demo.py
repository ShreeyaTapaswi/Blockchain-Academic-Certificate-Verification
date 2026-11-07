"""Demo: issue, verify, tamper-detect and revoke certificates."""
from blockchain import Blockchain, Institution, Transaction, certificate_hash


def issue(chain, inst, **cert):
    h = certificate_hash(institution=inst.name, **cert)
    tx = Transaction("ISSUE", h, inst.public_key_hex, inst.sign(f"ISSUE:{h}"))
    chain.add_transaction(tx)
    return h


def main():
    print("=" * 60)
    print("CertChain - Blockchain Certificate Verification")
    print("=" * 60)
    chain = Blockchain()
    inst = Institution("Example University")
    chain.register_institution(inst)

    print("== 1. Issuing certificates ==")
    cert = dict(student_id="C2K24001", name="Asha Patil", course="B.Tech Computer Engineering",
                grade="First Class with Distinction", issue_date="2026-06-15")
    h1 = issue(chain, inst, **cert)
    h2 = issue(chain, inst, student_id="C2K24002", name="Rohan Deshmukh",
               course="B.Tech Computer Engineering", grade="First Class", issue_date="2026-06-15")
    block = chain.mine_pending()
    print(f"Mined block #{block.index} hash={block.hash[:16]}... ({len(block.transactions)} certificates)")

    print("\n== 2. Verifying a genuine certificate ==")
    print(chain.verify_certificate(h1))

    print("\n== 3. Verifying a forged certificate (grade changed) ==")
    forged = dict(cert, grade="Distinction with Honours")
    print(chain.verify_certificate(certificate_hash(institution=inst.name, **forged)))

    print("\n== 4. Unauthorised issuer is rejected ==")
    fake = Institution("Fake University")
    try:
        issue(chain, fake, student_id="X1", name="Mallory", course="PhD", grade="A", issue_date="2026-01-01")
    except PermissionError as e:
        print("Rejected:", e)

    print("\n== 5. Revoking a certificate ==")
    chain.add_transaction(Transaction("REVOKE", h2, inst.public_key_hex, inst.sign(f"REVOKE:{h2}")))
    chain.mine_pending()
    print(chain.verify_certificate(h2))

    print("\n== 6. Ledger integrity ==")
    print("Chain valid:", chain.is_chain_valid())
    chain.chain[1].transactions[0]["cert_hash"] = "0" * 64  # tamper with history
    print("Chain valid after tampering:", chain.is_chain_valid())


if __name__ == "__main__":
    main()
