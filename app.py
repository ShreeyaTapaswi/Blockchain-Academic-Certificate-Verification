"""[31474 - Shreeya Tapaswi]
Web application for the Academic Certificate Verification System.

Run:  python app.py          then open http://127.0.0.1:5000
      python app.py --lan    also reachable from phones on the same Wi-Fi
"""
import argparse
import csv
import io
import json
import re
import socket
import threading
import time
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, jsonify, render_template, request

from blockchain import (Blockchain, Institution, Transaction, certificate_hash,
                        merkle_levels, tx_hash, verify_signature)

app = Flask(__name__)

DATA_FILE = Path(__file__).with_name("data.json")
LOCK = threading.RLock()
DEFAULT_INSTITUTION = "Pune Institute of Computer Technology"
FIELDS = ("student_id", "name", "course", "grade", "issue_date")
HASH_RE = re.compile(r"^[0-9a-f]{64}$")

state = {"chain": None, "institutions": {}, "records": {}, "log": [], "backup": None}


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ state
def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "institution"


def add_institution(name):
    name = name.strip()
    if not name:
        raise ValueError("Enter an institution name")
    iid = slug(name)
    if iid in state["institutions"]:
        raise ValueError("This institution is already registered")
    inst = Institution(name)
    state["chain"].register_institution(inst)
    state["institutions"][iid] = inst
    return iid


def new_state():
    state.update(chain=Blockchain(), institutions={}, records={}, log=[], backup=None)
    add_institution(DEFAULT_INSTITUTION)


def save():
    data = {
        "institutions": [{"id": i, "name": inst.name, "private": inst.private_hex()}
                         for i, inst in state["institutions"].items()],
        "chain": state["chain"].to_dict(),
        "records": state["records"], "log": state["log"], "backup": state["backup"],
    }
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(DATA_FILE)


def load():
    try:
        data = json.loads(DATA_FILE.read_text())
        state["institutions"] = {d["id"]: Institution(d["name"], d["private"])
                                 for d in data["institutions"]}
        state["chain"] = Blockchain.from_dict(data["chain"])
        state["records"] = data["records"]
        state["log"] = data["log"]
        state["backup"] = data["backup"]
        return True
    except (OSError, ValueError, KeyError):
        return False


def log(kind, text):
    state["log"].append({"t": time.strftime("%H:%M:%S"), "kind": kind, "text": text})
    del state["log"][:-80]


def api(fn):
    """Serialise access, turn errors into JSON."""
    @wraps(fn)
    def wrapper(*a, **k):
        with LOCK:
            try:
                return fn(*a, **k)
            except ApiError as e:
                return jsonify(ok=False, error=str(e)), e.status
            except (ValueError, PermissionError) as e:
                return jsonify(ok=False, error=str(e)), 400
    return wrapper


def guard():
    if state["backup"] is not None:
        raise ApiError("The ledger is tampered with. Undo the tampering first (Ledger tab).", 409)


def get_inst(iid):
    inst = state["institutions"].get(iid or "")
    if not inst:
        raise ValueError("Select an institution")
    return inst


def fields_from(data):
    f = {k: str(data.get(k, "")).strip() for k in FIELDS}
    if not all(f.values()):
        raise ValueError("Please fill in all certificate fields")
    return f


def block_view(b):
    return {"index": b.index, "hash": b.hash, "previous_hash": b.previous_hash,
            "merkle_root": b.merkle_root, "nonce": b.nonce, "difficulty": b.difficulty,
            "timestamp": b.timestamp, "tx_count": len(b.transactions)}


def mine_now():
    chain = state["chain"]
    n = len(chain.pending)
    if not n:
        raise ValueError("No pending transactions to mine")
    t0 = time.perf_counter()
    block = chain.mine_pending()
    view = block_view(block)
    view["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    view["attempts"] = block.nonce + 1
    log("mine", f"Block #{block.index} mined with {n} transaction(s) after {block.nonce + 1:,} attempts")
    return view


def issue_cert(iid, f):
    inst = get_inst(iid)
    h = certificate_hash(institution=inst.name, **f)
    state["chain"].add_transaction(Transaction("ISSUE", h, inst.public_key_hex, inst.sign(f"ISSUE:{h}")))
    state["records"][h] = {**f, "institution": inst.name, "institution_id": iid}
    log("issue", f"{inst.name} issued a certificate to {f['name']}")
    return h


def status_of(h):
    rec = state["chain"].find(h)
    if rec is None:
        return "pending" if state["chain"].is_pending(h) else "unknown", None
    return ("revoked" if rec["revoked"] else "valid"), rec


def run_verify(h, details=None):
    chain = state["chain"]
    steps = []

    def step(label, ok, detail=""):
        steps.append({"label": label, "ok": ok, "detail": detail})

    step("Recompute the SHA-256 fingerprint from the certificate details" if details
         else "Use the certificate fingerprint supplied", True, h)
    rec = chain.find(h)
    later = ["Confirm the issuer is an authorised institution",
             "Check the issuer's digital signature",
             "Check the block's integrity (hash, Merkle root, link)",
             "Check the certificate has not been revoked"]
    base = {"cert_hash": h, "details": state["records"].get(h), "steps": steps}
    if rec is None:
        pending = chain.is_pending(h)
        step("Look up the fingerprint on the ledger", False,
             "Waiting in the pending pool - not yet mined into a block" if pending
             else "No block contains this fingerprint")
        for label in later:
            step(label, None, "Skipped")
        return {**base, "valid": False, "pending": pending,
                "reason": "Issued but not yet mined into a block" if pending
                else "Certificate not found on the ledger"}
    step("Look up the fingerprint on the ledger", True, f"Found in block #{rec['block']}")
    name = chain.authorised_issuers.get(rec["issuer"])
    step(later[0], bool(name), name or "Unknown issuer")
    sig_ok = verify_signature(rec["issuer"], f"ISSUE:{h}", rec["signature"])
    step(later[1], sig_ok, "Ed25519 signature matches the issuer's public key" if sig_ok
         else "Signature does not match")
    issues = [i for i in chain.validate() if i["block"] == rec["block"]]
    step(later[2], not issues, "Block is intact" if not issues else issues[0]["message"])
    step(later[3], not rec["revoked"],
         "Not revoked" if not rec["revoked"] else f"Revoked in block #{rec['revoked_block']}")
    valid = all(s["ok"] for s in steps)
    reasons = ["Issuer is not authorised", "Signature is invalid",
               "Ledger integrity check failed for this block", "Certificate has been revoked"]
    reason = "Certificate is authentic"
    if not valid:
        reason = next((r for r, s in zip(reasons, steps[2:]) if not s["ok"]), "Verification failed")
    return {**base, "valid": valid, "reason": reason, "institution": name,
            "block": rec["block"], "timestamp": rec["timestamp"], "revoked": rec["revoked"]}


def hash_from_request(d):
    """Certificate hash from a pasted hash or from the entered details."""
    pasted = str(d.get("cert_hash", "")).strip().lower()
    if pasted:
        return pasted, None
    f = fields_from(d)
    inst_name = str(d.get("institution", "")).strip()
    if not inst_name:
        raise ValueError("Enter the issuing institution")
    return certificate_hash(institution=inst_name, **f), f


def stats():
    chain = state["chain"]
    issues = chain.validate()
    counts = {"valid": 0, "revoked": 0, "pending": 0}
    for h in state["records"]:
        s, _ = status_of(h)
        if s in counts:
            counts[s] += 1
    return {"blocks": len(chain.chain) - 1, "certificates": len(state["records"]),
            "valid": counts["valid"], "revoked": counts["revoked"],
            "pending": len(chain.pending), "institutions": len(state["institutions"]),
            "difficulty": chain.difficulty, "chain_valid": not issues,
            "issues": len(issues), "tampered": state["backup"] is not None}


# ------------------------------------------------------------------ pages
@app.route("/")
def index():
    return render_template("index.html")


@app.get("/verify/<h>")
def page_verify(h):
    if not HASH_RE.match(h):
        abort(404)
    with LOCK:
        result = run_verify(h)
    return render_template("verify.html", r=result)


@app.get("/certificate/<h>")
def page_certificate(h):
    if not HASH_RE.match(h):
        abort(404)
    with LOCK:
        result = run_verify(h)
    return render_template("certificate.html", r=result,
                           verify_url=request.host_url + "verify/" + h)


def qr_svg(text):
    try:
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode()
    except Exception:
        return None


@app.get("/qr/<h>")
def qr(h):
    if not HASH_RE.match(h):
        abort(404)
    svg = qr_svg(request.host_url + "verify/" + h)
    if not svg:
        abort(404)
    return Response(svg, mimetype="image/svg+xml")


# ------------------------------------------------------------------ read API
@app.get("/api/state")
@api
def api_state():
    chain = state["chain"]
    issued = {}
    for h in state["records"]:
        iid = state["records"][h]["institution_id"]
        issued[iid] = issued.get(iid, 0) + 1
    institutions = [{"id": i, "name": inst.name, "public_key": inst.public_key_hex,
                     "issued": issued.get(i, 0)} for i, inst in state["institutions"].items()]
    pending = [{"kind": p.kind, "cert_hash": p.cert_hash,
                "issuer": chain.authorised_issuers.get(p.issuer, "Unknown"),
                "details": state["records"].get(p.cert_hash)} for p in chain.pending]
    return jsonify(stats=stats(), institutions=institutions, pending=pending,
                   log=list(reversed(state["log"]))[:40])


@app.get("/api/ledger")
@api
def api_ledger():
    chain = state["chain"]
    issues = chain.validate()
    blocks = []
    for b in chain.chain:
        leaves = [tx_hash(t) for t in b.transactions]
        levels = merkle_levels(leaves)
        txs = [{"kind": t["kind"], "cert_hash": t["cert_hash"],
                "issuer": chain.authorised_issuers.get(t["issuer"], "Unknown"),
                "details": state["records"].get(t["cert_hash"])} for t in b.transactions]
        blocks.append({**block_view(b), "transactions": txs, "merkle_levels": levels,
                       "computed_merkle_root": levels[-1][0],
                       "issues": [i for i in issues if i["block"] == b.index]})
    return jsonify(valid=not issues, issues=issues, blocks=blocks,
                   tampered=state["backup"] is not None)


@app.get("/api/registry")
@api
def api_registry():
    q = request.args.get("q", "").lower().strip()
    rows = []
    for h, d in state["records"].items():
        s, rec = status_of(h)
        hay = " ".join(str(d[k]).lower() for k in ("student_id", "name", "course", "institution")) + " " + h
        if q and q not in hay:
            continue
        rows.append({**d, "cert_hash": h, "status": s, "block": rec["block"] if rec else None})
    rows.reverse()
    return jsonify(rows=rows)


@app.post("/api/sha256")
@api
def api_sha256():
    from blockchain import sha256
    texts = (request.json or {}).get("texts", [])
    return jsonify(hashes=[sha256(str(t)) for t in texts[:4]])


# ------------------------------------------------------------------ actions
@app.post("/api/institution")
@api
def api_institution():
    guard()
    iid = add_institution((request.json or {}).get("name", ""))
    log("institution", f"Registered institution: {state['institutions'][iid].name}")
    save()
    return jsonify(ok=True, id=iid)


@app.post("/api/issue")
@api
def api_issue():
    guard()
    d = request.json or {}
    h = issue_cert(d.get("institution_id"), fields_from(d))
    block = mine_now() if d.get("mine") else None
    save()
    return jsonify(ok=True, cert_hash=h, block=block, pending=len(state["chain"].pending))


@app.post("/api/bulk")
@api
def api_bulk():
    guard()
    d = request.json or {}
    get_inst(d.get("institution_id"))
    rows = [r for r in csv.reader(io.StringIO(d.get("csv", ""))) if any(c.strip() for c in r)]
    if rows and rows[0][0].strip().lower() in ("student_id", "id"):
        rows = rows[1:]
    errors, hashes = [], []
    for n, r in enumerate(rows, 1):
        if len(r) != 5 or not all(c.strip() for c in r):
            errors.append(f"Row {n}: expected 5 values (student_id, name, course, grade, issue_date)")
            continue
        try:
            hashes.append(issue_cert(d["institution_id"], dict(zip(FIELDS, (c.strip() for c in r)))))
        except (ValueError, PermissionError) as e:
            errors.append(f"Row {n}: {e}")
    if not hashes:
        raise ValueError("; ".join(errors) or "Nothing to issue - paste at least one row")
    block = mine_now()
    save()
    return jsonify(ok=True, added=len(hashes), errors=errors, block=block, hashes=hashes)


@app.post("/api/mine")
@api
def api_mine():
    guard()
    block = mine_now()
    save()
    return jsonify(ok=True, block=block)


@app.post("/api/difficulty")
@api
def api_difficulty():
    n = int((request.json or {}).get("difficulty", 3))
    if not 1 <= n <= 4:
        raise ValueError("Difficulty must be between 1 and 4")
    state["chain"].difficulty = n
    log("config", f"Mining difficulty set to {n} leading zeros")
    save()
    return jsonify(ok=True)


@app.post("/api/verify")
@api
def api_verify():
    h, details = hash_from_request(request.json or {})
    result = run_verify(h, details)
    log("verify", f"Verification {'PASSED' if result['valid'] else 'FAILED'}: {result['reason']}")
    save()
    return jsonify(ok=True, **result)


@app.post("/api/revoke")
@api
def api_revoke():
    guard()
    h, _ = hash_from_request(request.json or {})
    rec = state["chain"].find(h)
    if rec is None:
        raise ValueError("Certificate not found on the ledger (if it was just issued, mine the block first)")
    inst = next((i for i in state["institutions"].values() if i.public_key_hex == rec["issuer"]), None)
    if inst is None:
        raise ValueError("The issuing institution is not registered here")
    state["chain"].add_transaction(Transaction("REVOKE", h, inst.public_key_hex, inst.sign(f"REVOKE:{h}")))
    name = (state["records"].get(h) or {}).get("name", h[:10])
    log("revoke", f"{inst.name} revoked the certificate of {name}")
    block = mine_now()
    save()
    return jsonify(ok=True, block=block)


@app.post("/api/attack")
@api
def api_attack():
    kind = (request.json or {}).get("type")
    chain = state["chain"]
    first = next(iter(state["records"]), None)

    def result(blocked, title, attempt, response):
        log("attack", f"{'Blocked' if blocked else 'NOT blocked'}: {title}")
        save()
        return jsonify(ok=True, blocked=blocked, title=title, attempt=attempt, response=response)

    if kind == "fake_issuer":
        fake = Institution("Fake University")
        h = certificate_hash("X1", "Mallory", "PhD Computer Science", "A+", "2026-01-01", fake.name)
        try:
            chain.add_transaction(Transaction("ISSUE", h, fake.public_key_hex, fake.sign(f"ISSUE:{h}")))
        except PermissionError as e:
            return result(True, "Fake university issues a degree",
                          "'Fake University' signs a PhD certificate with its own valid key.", str(e))
    elif kind == "bad_signature":
        real = next(iter(state["institutions"].values()))
        thief = Institution("Thief")
        h = certificate_hash("X2", "Mallory", "B.Tech", "A+", "2026-01-01", real.name)
        try:
            chain.add_transaction(Transaction("ISSUE", h, real.public_key_hex, thief.sign(f"ISSUE:{h}")))
        except ValueError as e:
            return result(True, "Forged institution signature",
                          f"Attacker claims to be {real.name} but signs with a different private key.", str(e))
    elif kind == "duplicate":
        if not first:
            raise ValueError("Issue a certificate first, then try this attack")
        d = state["records"][first]
        inst = get_inst(d["institution_id"])
        try:
            chain.add_transaction(Transaction("ISSUE", first, inst.public_key_hex, inst.sign(f"ISSUE:{first}")))
        except ValueError as e:
            return result(True, "Re-issue (replay) an existing certificate",
                          f"The same certificate for {d['name']} is submitted a second time.", str(e))
    elif kind == "wrong_revoker":
        pair = None
        for h, d in state["records"].items():
            other = next((i for i, x in state["institutions"].items() if i != d["institution_id"]), None)
            if other and chain.find(h) and not chain.find(h)["revoked"]:
                pair = (h, d, state["institutions"][other])
                break
        if not pair:
            raise ValueError("Needs two institutions and one valid certificate - use 'Load sample data'")
        h, d, thief = pair
        try:
            chain.add_transaction(Transaction("REVOKE", h, thief.public_key_hex, thief.sign(f"REVOKE:{h}")))
        except PermissionError as e:
            return result(True, "Rival institution revokes someone else's certificate",
                          f"{thief.name} tries to revoke the certificate of {d['name']} ({d['institution']}).", str(e))
    elif kind == "forged_certificate":
        if not first:
            raise ValueError("Issue a certificate first, then try this attack")
        d = dict(state["records"][first])
        original_grade = d["grade"]
        d["grade"] = "Distinction with Honours" if original_grade != "Distinction with Honours" else "Pass"
        h = certificate_hash(institution=d["institution"], **{k: d[k] for k in FIELDS})
        res = run_verify(h, d)
        return result(not res["valid"], "Present a certificate with an upgraded grade",
                      f"Grade changed from '{original_grade}' to '{d['grade']}' on a genuine certificate.",
                      res["reason"])
    else:
        raise ValueError("Unknown attack")
    return result(False, "Attack", "", "The system accepted the transaction")


@app.post("/api/tamper")
@api
def api_tamper():
    if state["backup"] is not None:
        raise ApiError("The ledger is already tampered with. Undo it first.", 409)
    d = request.json or {}
    chain = state["chain"]
    backup = chain.to_dict()
    info = chain.tamper_block(int(d.get("block", 1)), smart=bool(d.get("smart")))
    state["backup"] = backup
    log("attack", f"Attacker edited a transaction in block #{info['block']}"
        + (" and re-mined that block" if info["smart"] else ""))
    save()
    return jsonify(ok=True, **info)


@app.post("/api/undo_tamper")
@api
def api_undo_tamper():
    if state["backup"] is None:
        raise ValueError("Nothing to undo")
    state["chain"] = Blockchain.from_dict(state["backup"])
    state["backup"] = None
    log("config", "Tampering undone - original ledger restored")
    save()
    return jsonify(ok=True)


@app.post("/api/reset")
@api
def api_reset():
    new_state()
    save()
    return jsonify(ok=True)


SAMPLE = [
    ("pune-institute-of-computer-technology", [
        ("C2K24001", "Asha Patil", "B.Tech Computer Engineering", "First Class with Distinction", "2026-06-15"),
        ("C2K24002", "Rohan Deshmukh", "B.Tech Computer Engineering", "First Class", "2026-06-15"),
        ("C2K24003", "Meera Kulkarni", "B.Tech Computer Engineering", "Distinction", "2026-06-15")]),
    ("iit-madras", [
        ("21F1000123", "Vikram Rao", "B.S. Data Science and Applications", "A", "2026-06-20"),
        ("21F1000456", "Priya Nair", "B.S. Data Science and Applications", "B+", "2026-06-20")]),
    ("savitribai-phule-pune-university", [
        ("S2K24777", "Neha Joshi", "M.Sc. Computer Science", "A+", "2026-05-30")]),
]


@app.post("/api/seed")
@api
def api_seed():
    new_state()
    add_institution("IIT Madras")
    add_institution("Savitribai Phule Pune University")
    first_hash = None
    for iid, certs in SAMPLE:
        for c in certs:
            h = issue_cert(iid, dict(zip(FIELDS, c)))
            first_hash = first_hash or h
        mine_now()
    # revoke Rohan's certificate, leave one certificate in the pending pool
    rohan = next(h for h, d in state["records"].items() if d["name"] == "Rohan Deshmukh")
    inst = state["institutions"]["pune-institute-of-computer-technology"]
    state["chain"].add_transaction(Transaction("REVOKE", rohan, inst.public_key_hex, inst.sign(f"REVOKE:{rohan}")))
    log("revoke", f"{inst.name} revoked the certificate of Rohan Deshmukh")
    mine_now()
    issue_cert("pune-institute-of-computer-technology",
               dict(zip(FIELDS, ("C2K24004", "Karan Mehta", "B.Tech Computer Engineering", "First Class", "2026-06-15"))))
    save()
    return jsonify(ok=True)


# ------------------------------------------------------------------ startup
if not load():
    new_state()
    save()


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lan", action="store_true", help="listen on the local network (phone QR scanning)")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    print("=" * 60)
    print(" CertChain - 31474 - Shreeya Tapaswi")
    print(f" Open http://127.0.0.1:{args.port}")
    if args.lan:
        print(f" On your phone (same Wi-Fi): http://{lan_ip()}:{args.port}")
    print("=" * 60)
    app.run(host="0.0.0.0" if args.lan else "127.0.0.1", port=args.port, debug=False)
