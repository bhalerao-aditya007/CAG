"""PWD Audit Red Flag Detection API."""
from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId
from io import BytesIO

from auth import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    set_auth_cookies, clear_auth_cookies, get_current_user, seed_admin,
)
from rules_data import RULES, RULES_BY_ID
from parsers import parse_file
from rules_engine import evaluate
from report_generator import build_report

# ---------------- Setup ----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="PWD Audit API")
api = APIRouter(prefix="/api")


async def current_user(request: Request) -> dict:
    return await get_current_user(request, db)


# ---------------- Models ----------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class AuditSessionCreate(BaseModel):
    division_name: str
    ddo_code: str = ""
    audit_period: str = ""
    auditor_name: str = ""
    notes: str = ""


class AuditSessionOut(BaseModel):
    id: str
    division_name: str
    ddo_code: str
    audit_period: str
    auditor_name: str
    notes: str
    file_count: int
    transaction_count: int
    flag_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: str
    status: str


# ---------------- Helpers ----------------
def _session_to_out(s: dict) -> dict:
    return {
        "id": s.get("id") or str(s.get("_id")),
        "division_name": s.get("division_name", ""),
        "ddo_code": s.get("ddo_code", ""),
        "audit_period": s.get("audit_period", ""),
        "auditor_name": s.get("auditor_name", ""),
        "notes": s.get("notes", ""),
        "file_count": s.get("file_count", 0),
        "transaction_count": s.get("transaction_count", 0),
        "flag_count": s.get("flag_count", 0),
        "critical_count": s.get("critical_count", 0),
        "high_count": s.get("high_count", 0),
        "medium_count": s.get("medium_count", 0),
        "low_count": s.get("low_count", 0),
        "created_at": s.get("created_at", ""),
        "status": s.get("status", "draft"),
    }


# ---------------- Auth Routes ----------------
@api.post("/auth/register")
async def register(body: RegisterIn, response: Response):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    doc = {
        "email": email,
        "password_hash": hash_password(body.password),
        "name": body.name,
        "role": "auditor",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    res = await db.users.insert_one(doc)
    uid = str(res.inserted_id)
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
    return {"id": uid, "email": email, "name": body.name, "role": "auditor"}


@api.post("/auth/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    uid = str(user["_id"])
    set_auth_cookies(response, create_access_token(uid, email), create_refresh_token(uid))
    return {"id": uid, "email": email, "name": user.get("name", ""), "role": user.get("role", "auditor")}


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(current_user)):
    return user


# ---------------- Rules ----------------
@api.get("/rules")
async def list_rules():
    return RULES


# ---------------- Audit Sessions ----------------
@api.post("/audit/sessions")
async def create_session(body: AuditSessionCreate, user: dict = Depends(current_user)):
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "user_id": user["id"],
        "division_name": body.division_name,
        "ddo_code": body.ddo_code,
        "audit_period": body.audit_period,
        "auditor_name": body.auditor_name or user.get("name", ""),
        "notes": body.notes,
        "file_count": 0,
        "transaction_count": 0,
        "flag_count": 0,
        "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0,
        "files": [],
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.audit_sessions.insert_one(doc)
    return _session_to_out(doc)


@api.get("/audit/sessions")
async def list_sessions(user: dict = Depends(current_user)):
    cursor = db.audit_sessions.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
    sessions = await cursor.to_list(500)
    return [_session_to_out(s) for s in sessions]


@api.get("/audit/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(current_user)):
    s = await db.audit_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_out(s) | {"files": s.get("files", [])}


@api.delete("/audit/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(current_user)):
    res = await db.audit_sessions.delete_one({"id": session_id, "user_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.transactions.delete_many({"session_id": session_id})
    await db.red_flags.delete_many({"session_id": session_id})
    return {"ok": True}


@api.post("/audit/sessions/{session_id}/upload")
async def upload_files(
    session_id: str,
    files: List[UploadFile] = File(...),
    declared_type: Optional[str] = Form(None),
    user: dict = Depends(current_user),
):
    s = await db.audit_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    added_tx = 0
    file_records = s.get("files", [])
    for up in files:
        content = await up.read()
        try:
            txs = parse_file(content, up.filename, declared_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse {up.filename}: {e}")
        for t in txs:
            t["id"] = str(uuid.uuid4())
            t["session_id"] = session_id
            t["created_at"] = datetime.now(timezone.utc).isoformat()
        if txs:
            await db.transactions.insert_many(txs)
            added_tx += len(txs)
        file_records.append({
            "name": up.filename,
            "size": len(content),
            "rows_parsed": len(txs),
            "declared_type": declared_type or "auto",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        })

    await db.audit_sessions.update_one(
        {"id": session_id},
        {"$set": {"files": file_records, "file_count": len(file_records)}, "$inc": {"transaction_count": added_tx}},
    )
    return {"ok": True, "transactions_added": added_tx, "total_files": len(file_records)}


@api.post("/audit/sessions/{session_id}/run")
async def run_analysis(session_id: str, user: dict = Depends(current_user)):
    s = await db.audit_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    cursor = db.transactions.find({"session_id": session_id}, {"_id": 0})
    txs = await cursor.to_list(10000)
    flags = evaluate(txs)
    # delete previous flags
    await db.red_flags.delete_many({"session_id": session_id})
    for f in flags:
        f["session_id"] = session_id
        f["created_at"] = datetime.now(timezone.utc).isoformat()
    if flags:
        await db.red_flags.insert_many([{**f} for f in flags])
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in flags:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    await db.audit_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "flag_count": len(flags),
            "critical_count": counts["critical"],
            "high_count": counts["high"],
            "medium_count": counts["medium"],
            "low_count": counts["low"],
            "status": "completed",
            "last_run_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"flag_count": len(flags), **{f"{k}_count": v for k, v in counts.items()}}


@api.get("/audit/sessions/{session_id}/flags")
async def list_flags(session_id: str, user: dict = Depends(current_user)):
    s = await db.audit_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    cursor = db.red_flags.find({"session_id": session_id}, {"_id": 0})
    flags = await cursor.to_list(5000)
    # enrich with rule meta
    for f in flags:
        meta = RULES_BY_ID.get(f["rule_id"], {})
        f["rule_criteria"] = meta.get("criteria", "")
        f["rule_source"] = meta.get("source", "")
        f["rule_parameter"] = meta.get("parameter", "")
    return flags


@api.get("/audit/sessions/{session_id}/transactions")
async def list_transactions(session_id: str, user: dict = Depends(current_user)):
    s = await db.audit_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    cursor = db.transactions.find({"session_id": session_id}, {"_id": 0, "_raw": 0})
    return await cursor.to_list(5000)


@api.get("/audit/sessions/{session_id}/report")
async def download_report(session_id: str, user: dict = Depends(current_user)):
    s = await db.audit_sessions.find_one({"id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    flags = await db.red_flags.find({"session_id": session_id}, {"_id": 0}).to_list(5000)
    txs = await db.transactions.find({"session_id": session_id}, {"_id": 0}).to_list(10000)
    pdf = build_report(s, flags, txs)
    filename = f"audit_report_{s.get('division_name','division').replace(' ','_')}_{session_id[:8]}.pdf"
    return StreamingResponse(
        BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------- Dashboard stats ----------------
@api.get("/stats/overview")
async def stats_overview(user: dict = Depends(current_user)):
    sessions = await db.audit_sessions.find({"user_id": user["id"]}, {"_id": 0}).to_list(1000)
    total_flags = sum(s.get("flag_count", 0) for s in sessions)
    crit = sum(s.get("critical_count", 0) for s in sessions)
    high = sum(s.get("high_count", 0) for s in sessions)
    med = sum(s.get("medium_count", 0) for s in sessions)
    total_tx = sum(s.get("transaction_count", 0) for s in sessions)
    # rule-wise distribution across all user's flags
    by_rule = {}
    async for f in db.red_flags.find({"session_id": {"$in": [s["id"] for s in sessions]}}, {"_id": 0, "rule_code": 1, "severity": 1}):
        by_rule[f["rule_code"]] = by_rule.get(f["rule_code"], 0) + 1
    recent = sorted(sessions, key=lambda s: s.get("created_at", ""), reverse=True)[:5]
    return {
        "total_sessions": len(sessions),
        "total_transactions": total_tx,
        "total_flags": total_flags,
        "critical_count": crit, "high_count": high, "medium_count": med,
        "by_rule": by_rule,
        "recent_sessions": [_session_to_out(s) for s in recent],
    }


# ---------------- Startup ----------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("pwd-audit")


@app.on_event("startup")
async def on_startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.audit_sessions.create_index([("user_id", 1), ("created_at", -1)])
        await db.transactions.create_index("session_id")
        await db.red_flags.create_index("session_id")
    except Exception as e:
        log.warning(f"Index creation: {e}")
    await seed_admin(db)
    # write test credentials file
    creds_path = Path("/app/memory/test_credentials.md")
    creds_path.parent.mkdir(parents=True, exist_ok=True)
    creds_path.write_text(
        "# Test Credentials\n\n"
        "## Admin Auditor\n"
        f"- Email: `{os.environ.get('ADMIN_EMAIL')}`\n"
        f"- Password: `{os.environ.get('ADMIN_PASSWORD')}`\n"
        "- Role: admin\n\n"
        "## Auth Endpoints\n"
        "- POST `/api/auth/register`\n"
        "- POST `/api/auth/login`\n"
        "- POST `/api/auth/logout`\n"
        "- GET `/api/auth/me`\n"
    )


@app.on_event("shutdown")
async def on_shutdown():
    client.close()


@api.get("/")
async def root():
    return {"service": "PWD Audit API", "version": "1.0"}
