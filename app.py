"""[31474 - Shreeya Tapaswi]
Web UI for the Academic Certificate Verification System.

Run:  python app.py   then open http://127.0.0.1:5000
"""
from flask import Flask, jsonify, render_template, request

from blockchain import Blockchain, Institution, Transaction, certificate_hash

app = Flask(__name__)

INSTITUTION_NAME = "Pune Institute of Computer Technology"
state = {}


def reset_state():
    chain = Blockchain()
    inst = Institution(INSTITUTION_NAME)
    chain.register_institution(inst)
    state["chain"] = chain
    state["inst"] = inst


reset_state()


def hash_from(data):
    fields = ("student_id", "name", "course", "grade", "issue_date")
    if any(not str(data.get(f, "")).strip() for f in fields):
        raise ValueError("Please fill in all certificate fields")
    return certificate_hash(institution=INSTITUTION_NAME,
                            **{f: data[f].strip() for f in fields})


@app.route("/")
def index():
    return render_template("index.html", institution=INSTITUTION_NAME)


@app.post("/api/issue")
def api_issue():
    chain, inst = state["chain"], state["inst"]
    try:
        h = hash_from(request.json)
        chain.add_transaction(Transaction("ISSUE", h, inst.public_key_hex, inst.sign(f"ISSUE:{h}")))
        block = chain.mine_pending()
        return jsonify(ok=True, cert_hash=h, block=block.index, block_hash=block.hash)
    except (ValueError, PermissionError) as e:
        return jsonify(ok=False, error=str(e)), 400


@app.post("/api/verify")
def api_verify():
    data = request.json or {}
    try:
        h = data["cert_hash"].strip() if data.get("cert_hash") else hash_from(data)
    except ValueError as e:
        return jsonify(ok=False, error=str(e)), 400
    result = state["chain"].verify_certificate(h)
    result["cert_hash"] = h
    result.pop("issuer", None)
    return jsonify(ok=True, **result)


@app.post("/api/revoke")
def api_revoke():
    chain, inst = state["chain"], state["inst"]
    data = request.json or {}
    try:
        h = data["cert_hash"].strip() if data.get("cert_hash") else hash_from(data)
        chain.add_transaction(Transaction("REVOKE", h, inst.public_key_hex, inst.sign(f"REVOKE:{h}")))
        block = chain.mine_pending()
        return jsonify(ok=True, cert_hash=h, block=block.index)
    except (ValueError, PermissionError) as e:
        return jsonify(ok=False, error=str(e)), 400


@app.get("/api/ledger")
def api_ledger():
    chain = state["chain"]
    return jsonify(
        valid=chain.is_chain_valid(),
        blocks=[{"index": b.index, "hash": b.hash, "previous_hash": b.previous_hash,
                 "nonce": b.nonce, "timestamp": b.timestamp,
                 "transactions": [{"kind": t["kind"], "cert_hash": t["cert_hash"]}
                                  for t in b.transactions]}
                for b in chain.chain])


@app.post("/api/tamper")
def api_tamper():
    """Demo only: silently edit a transaction in the oldest block that has one."""
    for block in state["chain"].chain:
        if block.transactions:
            block.transactions[0]["cert_hash"] = "0" * 64
            return jsonify(ok=True, block=block.index)
    return jsonify(ok=False, error="Issue a certificate first"), 400


@app.post("/api/reset")
def api_reset():
    reset_state()
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=False)
