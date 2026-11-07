<p align="center">
  <img src="docs/banner.svg" alt="CertChain - Blockchain-based Academic Certificate Verification" width="100%">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-web%20app-000000?logo=flask&logoColor=white">
  <img alt="SHA-256" src="https://img.shields.io/badge/hashing-SHA--256-1f3864">
  <img alt="Ed25519" src="https://img.shields.io/badge/signatures-Ed25519-7b4dd6">
  <img alt="Tests" src="https://img.shields.io/badge/tests-32%20passing-1b7f3b">
  <img alt="Auth" src="https://img.shields.io/badge/admin-login%20protected-b3261e">
  <img alt="License" src="https://img.shields.io/github/license/ShreeyaTapaswi/Blockchain-Academic-Certificate-Verification">
</p>

<p align="center"><b>Verify any academic certificate in seconds: no phone calls, no paperwork, no forged grades.</b><br>
A permissioned blockchain where universities <i>issue</i> and <i>sign</i> certificates, and anyone on the internet can <i>verify</i> them.</p>

<p align="center">👩‍💻 <b>Author:</b> <a href="https://github.com/ShreeyaTapaswi">Shreeya Tapaswi</a> &nbsp;·&nbsp; Blockchain Technology Mini Project</p>

<!-- Live demo: add your deployed link here, e.g.  🌐 **Live demo:** https://your-app.onrender.com -->

---

## 📑 Contents
[The problem](#-the-problem) · [The solution](#-the-solution) · [Features](#-features) · [Screenshots](#-screenshots) · [How it works](#-how-it-works) · [Security model](#-security-model) · [Run locally](#-run-it-locally) · [Deploy](#%EF%B8%8F-deploy-render) · [Project structure](#-project-structure) · [Limitations](#-limitations--future-work)

---

## 📌 The problem
Fake degrees are a real, expensive problem. Verifying a certificate today means emailing the university, waiting days, and trusting a PDF or a paper stamp that is easy to forge.

## 💡 The solution
Each certificate is reduced to a **SHA-256 fingerprint** and recorded on a tamper-evident ledger by the issuing institution, **digitally signed with its private key**. Verification becomes a mathematical check anyone can run:

> *Is this exact certificate's fingerprint on the ledger, signed by an authorised institution, and not revoked?*

Change one character (a grade, a name, a date) and the fingerprint is completely different, so the check fails.

🔒 **Privacy by design:** only the hash goes on-chain. No names, grades or student IDs are ever stored in a block.

---

## ✨ Features

| | |
|---|---|
| 🌍 **Public verification** | Anyone can verify by details, fingerprint, or by scanning the certificate's QR code. No account needed. |
| 🔐 **Admin login** | Issuing, revoking, tampering and every other write action require an institution administrator login. |
| ✍️ **Issue** | Single or bulk (CSV) issuing, signed with the institution's Ed25519 key |
| 🔍 **Step-by-step verification** | Fingerprint → ledger lookup → issuer → signature → block integrity → revocation |
| 📄 **Printable certificate + QR** | Every certificate gets a public verify link and a scannable QR code |
| 🚫 **Revocation** | Only the *issuing* institution can revoke, and the revocation itself lives on the ledger |
| ⛓ **Ledger explorer** | Inspect every block, hash, nonce and the full **Merkle tree** |
| 🛡 **Security Lab** | Launch 5 real attacks and watch each one get blocked |
| 😈 **Tamper simulator** | A *naive* attacker breaks the Merkle root; a *smart* attacker who re-mines still breaks the next block's link |
| 🏛 **Multi-institution** | Register institutions, each with its own key pair |
| 🎓 **Guided demo** | Built-in walkthrough and projector mode for presentations |

---

## 📸 Screenshots

### 🌍 What the public sees
Anyone can verify a certificate; the admin console is hidden behind a login.

| Public verification | Institution login |
|---|---|
| ![Public verify](docs/screenshots/02-public-verify.png) | ![Login](docs/screenshots/01-login.png) |

<p align="center"><img src="docs/screenshots/16-mobile.png" width="260" alt="Mobile view"><br><sub>Fully responsive: works on a phone after scanning the QR code</sub></p>

### 🏛 Admin console
![Dashboard](docs/screenshots/03-dashboard.png)

<details open>
<summary><b>✍️ Issue &amp; 🔍 verify</b></summary>

**Issue a certificate**
![Issue](docs/screenshots/04-issue.png)

**Authentic ✅**
![Verify valid](docs/screenshots/05-verify-valid.png)

**Forged grade ❌**: upgrading *"First Class with Distinction"* to *"Distinction with Honours"* gives a different fingerprint that is not on the ledger.
![Verify forged](docs/screenshots/06-verify-forged.png)

**Revoked certificate**
![Verify revoked](docs/screenshots/07-verify-revoked.png)

**Registry**
![Registry](docs/screenshots/08-registry.png)
</details>

<details open>
<summary><b>⛓ Ledger, Merkle tree &amp; tamper detection</b></summary>

**Ledger explorer**
![Ledger](docs/screenshots/09-ledger.png)

**Tampered ledger: the chain visibly breaks** 🔴
![Tampered ledger](docs/screenshots/10-ledger-tampered.png)
</details>

<details>
<summary><b>🛡 Security Lab, institutions, learn tab, QR pages</b></summary>

**Security Lab: every attack blocked**
![Security lab](docs/screenshots/11-security-lab.png)

| Institutions | Learn |
|---|---|
| ![Institutions](docs/screenshots/12-institutions.png) | ![Learn](docs/screenshots/13-learn.png) |

| Shareable result page | Printable certificate with QR |
|---|---|
| ![Verify page](docs/screenshots/14-verify-page.png) | ![Certificate](docs/screenshots/15-certificate.png) |
</details>

---

## 🧠 How it works

```mermaid
flowchart LR
    A["🎓 Certificate details"] -->|SHA-256| B["🔑 Fingerprint"]
    B -->|"signed with Ed25519<br/>(institution key)"| C["📥 Pending pool"]
    C -->|"⛏ Proof of Work"| D["🧱 Block<br/>Merkle root + prev hash + nonce"]
    D --> E[("⛓ Ledger")]
    F["🕵️ Anyone"] -->|"details or QR"| G{"Re-hash and look up"}
    E --> G
    G --> H["✅ Authentic / ❌ Not valid"]
```

1. **Fingerprint:** `SHA-256` of the canonical JSON of the certificate (student ID, name, course, grade, date, institution).
2. **Sign:** the institution signs `ISSUE:<hash>` (or `REVOKE:<hash>`) with its **Ed25519** private key.
3. **Pending pool:** a certificate is *not valid* until its block is mined.
4. **Merkle root:** every block summarises all its transactions in one root hash.
5. **Proof of Work:** the block hash must start with N zeros (difficulty 1-4).
6. **Hash chain:** each block stores the previous block's hash, so rewriting history breaks every block after it.

### Why the attacks fail

| Attack | Defence |
|---|---|
| Unregistered "Fake University" issues a degree | Authorised-issuer registry |
| Attacker impersonates a real university | Ed25519 signature check |
| Same certificate submitted twice (replay) | Duplicate-fingerprint check |
| Rival institution revokes someone else's certificate | Only the original issuer may revoke |
| Grade or name altered on a real certificate | Different SHA-256, so it is not on the ledger |
| Old block edited (naive) | Merkle root mismatch |
| Old block edited **and re-mined** (smart) | Next block's `previous_hash` link breaks; the last block fails its signature check |

---

## 🔐 Security model

The ledger is protected at two levels: **cryptographically** (the blockchain) and **at the door** (the web app).

| Who | Can do | Cannot do |
|---|---|---|
| 🌍 **Anyone (no login)** | Verify certificates, open the shareable result page, view/print a certificate, scan QR codes | Issue, revoke, mine, reset, tamper, view the ledger, registry or keys |
| 🏛 **Administrator (login)** | Everything above plus issue, bulk issue, revoke, mine, register institutions, Security Lab, ledger explorer | n/a |

How the web app is hardened:

- **Secure by default:** a `before_request` hook protects *every* route unless it is on a short public allow-list, so a route added later can't be left open by mistake. This is covered by a test.
- **No default password:** set `ADMIN_PASSWORD`; if you don't, a random one is generated and printed in the server log.
- **Brute-force protection:** 5 failed logins locks that IP out for 5 minutes, with a small delay on each failure and constant-time credential comparison.
- **Session safety:** `HttpOnly`, `SameSite=Lax` and (on hosting) `Secure` cookies, an 8-hour expiry, and a 1 MB request limit.
- **Anonymous requests never write:** public verification does not touch the ledger or the activity log.
- **Hardening headers:** `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, and `no-store` caching.

---

## 🚀 Run it locally

```bash
git clone https://github.com/ShreeyaTapaswi/Blockchain-Academic-Certificate-Verification.git
cd Blockchain-Academic-Certificate-Verification

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# choose your admin login (optional locally)
export ADMIN_USER=admin                 # Windows PowerShell: $env:ADMIN_USER="admin"
export ADMIN_PASSWORD='choose-a-strong-password'

python app.py                    # → http://127.0.0.1:5000
python app.py --lan              # also reachable from a phone on the same Wi-Fi (QR scanning)
```

- Open `http://127.0.0.1:5000` to see the **public** page, or `/login` for the admin console.
- If you skip `ADMIN_PASSWORD`, the terminal prints a one-off generated password.
- After logging in, click **Load sample data** on the dashboard, or **Start guided demo**.

### Run the tests
```bash
python -m unittest -v
```
32 tests: 21 for the blockchain (issuing, revocation rules, signatures, Merkle roots, naive/smart tampering, persistence) and 11 for access control (anonymous users blocked from every write endpoint, brute-force lockout, public verification, default-deny).

---

## ☁️ Deploy (Render)

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:app --workers 1 --threads 4` |

**Environment variables** (Render → your service → *Environment*):

| Variable | Purpose |
|---|---|
| `ADMIN_PASSWORD` | **Required.** Your admin password. Use a long, unique one. |
| `ADMIN_USER` | Admin username (default `admin`) |
| `SECRET_KEY` | Random string that signs login cookies, e.g. output of `python -c "import secrets;print(secrets.token_hex(32))"` |
| `RENDER` | Set automatically by Render; enables secure cookies and correct `https` QR links |

**Clean URLs:** on Render the site is served at `https://certchain-6012.onrender.com` with no port number. Pick a short *Name* when creating the service (e.g. `certchain`) to get `https://certchain.onrender.com`. Handy short routes: `/` (public verification), `/verify`, `/login` and `/admin`. You can also attach your own domain under *Settings → Custom Domains*.

Use **one worker**: the ledger lives in a single process's memory and is saved to `data.json`. On free hosting the disk is ephemeral, so the ledger resets on redeploy. Log in and click **Load sample data** to refill it.

> ⚠️ Never commit `data.json`: it holds the institutions' private signing keys. It is already in `.gitignore`.

---

## 🗂 Project structure

```
├── app.py                 # Flask app: auth, pages and JSON API
├── blockchain.py          # Core: hashing, Merkle tree, signing, blocks, chain, validation
├── test_blockchain.py     # 21 blockchain tests
├── test_auth.py           # 11 access-control tests
├── templates/
│   ├── public.html        # Public verification landing page
│   ├── login.html         # Administrator login
│   ├── index.html         # Admin console (dashboard, issue, ledger, security lab…)
│   ├── verify.html        # Shareable result page (opened by the QR code)
│   └── certificate.html   # Printable certificate with QR
├── docs/                  # Banner and screenshots used in this README
└── requirements.txt
```

---

## 🧱 Limitations & future work

This is an educational **proof of concept** of a *permissioned* blockchain.

- Runs as a single node: no peer-to-peer network or consensus between nodes.
- Keys are held by the app for demo convenience. A real deployment keeps each institution's key in an HSM or on its own system.
- Proof of Work deters silent tampering; production permissioned networks usually use PBFT/Raft-style consensus.
- Certificate details are kept off-chain in the app's records; only fingerprints are on-chain.
- A single shared admin login stands in for per-institution accounts.

**Next steps:** per-institution logins and roles · multi-node network with consensus · hardware-backed keys · DigiLocker integration · Merkle inclusion proofs for light-client verification.

---

## 👩‍💻 Author

**Shreeya Tapaswi**: designed and built CertChain end to end (blockchain core, web app, security and UI) as a Blockchain Technology mini project.

[![GitHub](https://img.shields.io/badge/GitHub-ShreeyaTapaswi-181717?logo=github)](https://github.com/ShreeyaTapaswi)

<p align="center"><sub>⭐ If you found this useful, consider starring the repo.</sub></p>
