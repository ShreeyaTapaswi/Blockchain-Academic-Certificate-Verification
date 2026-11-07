# Blockchain-based Academic Certificate Verification System

**31474 - Shreeya Tapaswi**
Mini Project - Blockchain Technology, Pune Institute of Computer Technology (PICT)

A permissioned blockchain that lets an institution issue academic certificates and lets anyone verify them instantly. Only the SHA-256 hash of a certificate is stored on the ledger, so no personal data is exposed.

## Project files

| File | Purpose |
|---|---|
| `blockchain.py` | Core blockchain: blocks, transactions, proof of work, hashing, Ed25519 signatures, issuer registry |
| `app.py` | Flask web server with JSON API for the UI |
| `templates/index.html` | Web UI (Issue, Verify, Revoke, Ledger explorer) |
| `demo.py` | Command-line demonstration of every scenario |
| `test_blockchain.py` | 9 automated unit tests |
| `CertificateRegistry.sol` | Solidity smart contract version (deploy on Remix or any Ethereum network) |
| `requirements.txt` | Python dependencies (`cryptography`, `flask`) |
| `Certificate_Verification_Mini_Project_Report.docx` | Full project report |

## How to run

```
pip install -r requirements.txt
python app.py            # web UI at http://127.0.0.1:5000
python demo.py           # command-line demo
python -m unittest -v    # run the 9 tests
```

On Windows use `py` instead of `python` if needed. Keep `index.html` inside the `templates` folder.

## Features

**Blockchain core**
- Blocks linked by SHA-256 hashes, so any change to history is detectable
- Proof-of-work mining (difficulty 3 leading zeros)
- Genesis block and full chain validation (hash, proof-of-work and link checks)

**Certificate management**
- Issue: certificate fields are hashed and recorded in a new block
- Verify: recompute the hash from the printed certificate, or paste the hash directly
- Revoke: the issuing institution can revoke, and revoked certificates fail verification
- Duplicate issuance is rejected

**Security**
- Ed25519 digital signature on every transaction
- Only registered institutions (authorised public keys) can issue or revoke
- Only the original issuer can revoke its certificates
- Forged or altered certificates produce a different hash and are reported as not found
- Privacy preserving: only hashes are stored, never names or grades

**Web UI**
- Four tabs: Issue, Verify, Revoke, Ledger
- Green/red verification results with the block number and issuer
- Ledger explorer showing each block's hash, previous hash, nonce and transactions
- VALID/BROKEN chain status, with the tampered block highlighted
- "Tamper with a block" button to demonstrate tamper detection, and "Reset ledger"
- Responsive layout that also works on a phone

**Smart contract (Solidity)**
- Admin-controlled issuer whitelist
- `issueCertificate`, `revokeCertificate` and a read-only `verifyCertificate`
- Events emitted for issuing, revoking and issuer changes

**Testing**
- 9 unit tests: valid, unknown, tampered, unauthorised issuer, bad signature, duplicate, revoke, wrong revoker and chain tampering

## Demo flow for viva

1. Issue a certificate, then Verify (green).
2. Change the grade and Verify (red, not found).
3. Revoke, then Verify (revoked).
4. Open Ledger, click "Tamper with a block", and the chain shows BROKEN.
5. Reset ledger to start over.

## Limitations and future scope

- Single-node simulation (no peer-to-peer network); the ledger resets when the server restarts
- One built-in institution in the UI
- Future: QR codes on certificates, deployment on a testnet, IPFS for certificate PDFs, Merkle trees for batch issuance
