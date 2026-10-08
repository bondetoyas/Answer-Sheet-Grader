"""Automated Answer Sheet Grader - FastAPI backend."""

import json
import logging
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytesseract
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from grading import grade, split_sections
from security import (
    RateLimiter,
    create_token,
    hash_password,
    verify_password,
    verify_token,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("grader")

# --------------------------------------------------------------------------
# Configuration (all via environment variables)
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR))
DATABASE_FILE = DATA_DIR / "grader.db"
UPLOAD_DIR = DATA_DIR / "uploads"

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_HOURS", "12")) * 3600
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"PNG": ".png", "JPEG": ".jpg"}

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be set when ENVIRONMENT=production")
    SECRET_KEY = secrets.token_hex(32)
    log.warning("SECRET_KEY not set: using a random key (logins reset on restart).")

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    ).split(",")
    if o.strip()
]

SEMANTIC_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
semantic_model = None
semantic_unavailable = False

login_limiter = RateLimiter(limit=10, window_seconds=300)

TESSERACT_PATH = Path(
    os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
)
if TESSERACT_PATH.exists():
    pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
@contextmanager
def db():
    """Open a connection that commits on success, rolls back on error, always closes."""
    connection = sqlite3.connect(DATABASE_FILE, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with db() as con:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        user_columns = {r["name"] for r in con.execute("PRAGMA table_info(users)")}
        if "is_admin" not in user_columns:
            con.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        con.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id),
                student_name TEXT NOT NULL,
                question_title TEXT NOT NULL,
                model_answer TEXT NOT NULL,
                student_answer TEXT NOT NULL,
                rubric_json TEXT NOT NULL,
                image_path TEXT,
                ai_score REAL NOT NULL,
                final_score REAL NOT NULL,
                max_marks REAL NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Upgrade databases created by earlier versions.
        existing = {row["name"] for row in con.execute("PRAGMA table_info(submissions)")}
        for column, ddl in {
            "user_id": "INTEGER REFERENCES users(id)",
            "student_name": "TEXT NOT NULL DEFAULT 'Unknown student'",
            "question_title": "TEXT NOT NULL DEFAULT 'Untitled question'",
            "rubric_json": "TEXT NOT NULL DEFAULT '[]'",
            "image_path": "TEXT",
        }.items():
            if column not in existing:
                con.execute(f"ALTER TABLE submissions ADD COLUMN {column} {ddl}")

        con.execute("CREATE INDEX IF NOT EXISTS idx_sub_user ON submissions(user_id, id DESC)")

        # Bootstrap the first teacher account from the environment.
        admin_user = os.getenv("ADMIN_USERNAME")
        admin_pass = os.getenv("ADMIN_PASSWORD")
        if admin_user and admin_pass:
            if con.execute("SELECT 1 FROM users WHERE username = ?", (admin_user,)).fetchone() is None:
                create_user(con, admin_user, admin_pass, is_admin=True)
                log.info("Created bootstrap user %r", admin_user)

        # Make sure at least one admin exists (the oldest account).
        if con.execute("SELECT 1 FROM users WHERE is_admin = 1").fetchone() is None:
            con.execute("UPDATE users SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM users)")

        # Assign pre-login records to the first user so they are not orphaned.
        first = con.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        if first:
            con.execute("UPDATE submissions SET user_id = ? WHERE user_id IS NULL", (first["id"],))

        if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            log.warning(
                "No users exist. Set ADMIN_USERNAME/ADMIN_PASSWORD or run: python manage.py create-user"
            )


def create_user(con, username: str, password: str, is_admin: bool = False) -> int:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if not username.strip():
        raise ValueError("Username is required.")
    cur = con.execute(
        "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
        (username.strip(), hash_password(password), int(is_admin),
         datetime.now().isoformat(timespec="seconds")),
    )
    return cur.lastrowid


@asynccontextmanager
async def lifespan(_app):
    init_database()
    yield


app = FastAPI(title="Automated Answer Sheet Grader", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def current_user(request: Request) -> sqlite3.Row:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    user_id = verify_token(token, SECRET_KEY) if scheme.lower() == "bearer" else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    with db() as con:
        user = con.execute("SELECT id, username, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


def require_admin(user=Depends(current_user)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return user


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class NewUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    is_admin: bool = False


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


@app.post("/auth/login")
def login(data: LoginRequest, request: Request):
    client = request.client.host if request.client else "unknown"
    if not login_limiter.allow(client):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in a few minutes.")

    with db() as con:
        user = con.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (data.username.strip(),)
        ).fetchone()

    # Always run a hash check so response time does not reveal valid usernames.
    stored = user["password_hash"] if user else hash_password("dummy-password")
    ok = verify_password(data.password, stored)
    if not user or not ok:
        log.warning("Failed login for %r from %s", data.username[:50], client)
        raise HTTPException(status_code=401, detail="Incorrect username or password.")

    login_limiter.reset(client)
    return {
        "access_token": create_token(user["id"], SECRET_KEY, TOKEN_TTL_SECONDS),
        "token_type": "bearer",
        "username": user["username"],
    }


@app.get("/auth/me")
def me(user=Depends(current_user)):
    return {"username": user["username"], "is_admin": bool(user["is_admin"])}


@app.post("/auth/change-password")
def change_password(data: PasswordChangeRequest, user=Depends(current_user)):
    with db() as con:
        row = con.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not verify_password(data.current_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        con.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(data.new_password), user["id"]),
        )
    return {"message": "Password changed."}


@app.get("/admin/users")
def list_users(admin=Depends(require_admin)):
    with db() as con:
        rows = con.execute(
            """SELECT u.id, u.username, u.is_admin, u.created_at,
                      (SELECT COUNT(*) FROM submissions s WHERE s.user_id = u.id) AS submissions
               FROM users u ORDER BY u.id"""
        ).fetchall()
    return [{**dict(r), "is_admin": bool(r["is_admin"])} for r in rows]


@app.post("/admin/users")
def add_user(data: NewUserRequest, admin=Depends(require_admin)):
    try:
        with db() as con:
            user_id = create_user(con, data.username, data.password, data.is_admin)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="That username already exists.")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"message": "User created.", "user_id": user_id}


@app.post("/admin/users/{user_id}/reset-password")
def reset_password(user_id: int, data: PasswordResetRequest, admin=Depends(require_admin)):
    with db() as con:
        cur = con.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(data.new_password), user_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found.")
    return {"message": "Password reset."}


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class RubricItem(BaseModel):
    point: str = Field(min_length=1, max_length=300)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    semantic_reference: str = Field(default="", max_length=1000)
    marks: float = Field(gt=0, le=1000)


class GradeRequest(BaseModel):
    model_answer: str = Field(default="", max_length=20000)
    student_answer: str = Field(max_length=20000)
    rubric: list[RubricItem] = Field(max_length=50)


class SubmissionRequest(BaseModel):
    student_name: str = Field(min_length=1, max_length=200)
    question_title: str = Field(min_length=1, max_length=500)
    model_answer: str = Field(max_length=20000)
    student_answer: str = Field(max_length=20000)
    rubric: list[RubricItem] = Field(max_length=50)
    ai_score: float = Field(ge=0)
    final_score: float = Field(ge=0)
    max_marks: float = Field(gt=0)
    image_path: str | None = Field(default=None, max_length=300)


class SubmissionUpdateRequest(BaseModel):
    student_name: str | None = Field(default=None, min_length=1, max_length=200)
    question_title: str | None = Field(default=None, min_length=1, max_length=500)
    student_answer: str | None = Field(default=None, max_length=20000)
    final_score: float | None = Field(default=None, ge=0)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
@app.get("/")
def welcome():
    return {"message": "Answer Sheet Grader backend is running"}


@app.get("/health")
def health():
    try:
        with db() as con:
            con.execute("SELECT 1").fetchone()
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable.")
    return {"status": "ok"}


def owned_image_name(user_id: int, image_path: str | None) -> str | None:
    """Validate that image_path points at one of this user's uploads."""
    if not image_path:
        return None
    name = Path(image_path).name
    if not name.startswith(f"{user_id}_") or not (UPLOAD_DIR / name).is_file():
        raise HTTPException(status_code=400, detail="Unknown image reference.")
    return f"/uploads/{name}"


@app.post("/ocr")
def extract_text_from_image(
    file: UploadFile = File(...),
    store_image: bool = True,
    user=Depends(current_user),
):
    # Plain `def` -> FastAPI runs it in a worker thread, so slow OCR never blocks other requests.
    file_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image is larger than 10 MB.")

    try:
        image = Image.open(BytesIO(file_bytes))
        image_format = image.format
        if image_format not in ALLOWED_FORMATS:
            raise HTTPException(status_code=400, detail="Only PNG and JPEG images are supported.")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=400, detail="Image dimensions are too large.")
        image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(status_code=400, detail="The uploaded file is not a readable image.")

    stored_filename = f"{user['id']}_{uuid4().hex}{ALLOWED_FORMATS[image_format]}"
    if store_image:
        (UPLOAD_DIR / stored_filename).write_bytes(file_bytes)

    image = ImageOps.exif_transpose(image)
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    image = ImageEnhance.Contrast(image).enhance(2)
    image = image.filter(ImageFilter.SHARPEN)

    if image.width < 1600:
        scale = 1600 / image.width
        image = image.resize(
            (int(image.width * scale), int(image.height * scale)),
            Image.Resampling.LANCZOS,
        )
    image = image.point(lambda pixel: 0 if pixel < 170 else 255)

    try:
        extracted_text = pytesseract.image_to_string(
            image, lang="eng", config="--psm 6", timeout=60
        ).strip()
    except pytesseract.TesseractNotFoundError:
        if store_image:
            (UPLOAD_DIR / stored_filename).unlink(missing_ok=True)
        log.error("Tesseract not found")
        raise HTTPException(
            status_code=500,
            detail="Tesseract is not installed or its path is incorrect. "
                   "Install it or set the TESSERACT_CMD environment variable.",
        )
    except RuntimeError:  # pytesseract raises RuntimeError on timeout
        if store_image:
            (UPLOAD_DIR / stored_filename).unlink(missing_ok=True)
        raise HTTPException(status_code=504, detail="Text extraction timed out. Try a smaller image.")

    return {
        "filename": file.filename,
        "extracted_text": extracted_text,
        "image_path": f"/uploads/{stored_filename}" if store_image else None,
        "sections": split_sections(extracted_text),
    }


@app.get("/uploads/{filename}")
def get_upload(filename: str, user=Depends(current_user)):
    name = Path(filename).name
    path = UPLOAD_DIR / name
    if name != filename or not name.startswith(f"{user['id']}_") or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path)


@app.post("/grade")
def grade_answer(data: GradeRequest, user=Depends(current_user)):
    if not data.rubric:
        raise HTTPException(status_code=400, detail="Add at least one rubric point.")
    return grade(
        [item.model_dump() for item in data.rubric],
        data.student_answer,
        similarity_fn=calculate_semantic_similarities,
    )


@app.post("/submissions")
def save_submission(data: SubmissionRequest, user=Depends(current_user)):
    if not data.rubric:
        raise HTTPException(status_code=400, detail="Rubric cannot be empty.")
    if data.final_score > data.max_marks:
        raise HTTPException(status_code=400, detail="Final score must be between 0 and maximum marks.")

    image_path = owned_image_name(user["id"], data.image_path)

    with db() as con:
        cur = con.execute(
            """
            INSERT INTO submissions
            (user_id, student_name, question_title, model_answer, student_answer,
             rubric_json, image_path, ai_score, final_score, max_marks, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"], data.student_name.strip(), data.question_title.strip(),
                data.model_answer, data.student_answer,
                json.dumps([i.model_dump() for i in data.rubric]),
                image_path, data.ai_score, data.final_score, data.max_marks,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return {"message": "Grade saved successfully", "submission_id": cur.lastrowid}


@app.get("/submissions")
def get_submissions(limit: int = 200, offset: int = 0, user=Depends(current_user)):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    with db() as con:
        rows = con.execute(
            "SELECT * FROM submissions WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user["id"], limit, offset),
        ).fetchall()

    submissions = []
    for row in rows:
        item = dict(row)
        item.pop("user_id", None)
        try:
            item["rubric"] = json.loads(item.pop("rubric_json", "[]"))
        except json.JSONDecodeError:
            item["rubric"] = []
        submissions.append(item)
    return submissions


@app.put("/submissions/{submission_id}")
def update_submission(submission_id: int, data: SubmissionUpdateRequest, user=Depends(current_user)):
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Provide at least one field to update.")

    with db() as con:
        row = con.execute(
            "SELECT max_marks FROM submissions WHERE id = ? AND user_id = ?",
            (submission_id, user["id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found.")
        if "final_score" in updates and updates["final_score"] > row["max_marks"]:
            raise HTTPException(status_code=400, detail="Final score must be between 0 and maximum marks.")

        # Column names come from the fixed model fields above, never from user input.
        assignments = ", ".join(f"{column} = ?" for column in updates)
        con.execute(
            f"UPDATE submissions SET {assignments} WHERE id = ? AND user_id = ?",
            [*updates.values(), submission_id, user["id"]],
        )
    return {"message": "Submission updated successfully."}


@app.delete("/submissions/{submission_id}")
def delete_submission(submission_id: int, user=Depends(current_user)):
    with db() as con:
        row = con.execute(
            "SELECT image_path FROM submissions WHERE id = ? AND user_id = ?",
            (submission_id, user["id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Submission not found.")
        con.execute("DELETE FROM submissions WHERE id = ?", (submission_id,))

        image_path = row["image_path"]
        if image_path:
            still_used = con.execute(
                "SELECT 1 FROM submissions WHERE image_path = ?", (image_path,)
            ).fetchone()
            if not still_used:
                (UPLOAD_DIR / Path(image_path).name).unlink(missing_ok=True)
    return {"message": "Submission deleted successfully."}


# --------------------------------------------------------------------------
# Semantic matching (optional)
# --------------------------------------------------------------------------
def get_semantic_model():
    """Load SBERT lazily. Returns None (keyword-only grading) if unavailable."""
    global semantic_model, semantic_unavailable

    if semantic_unavailable:
        return None
    if semantic_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            semantic_model = SentenceTransformer(SEMANTIC_MODEL_NAME)
        except Exception as error:  # not installed, or model download failed
            semantic_unavailable = True
            log.warning("Semantic matching disabled: %s", error)
            return None
    return semantic_model


def calculate_semantic_similarities(student_answer, references):
    """Cosine similarity of the answer to each reference, or None if unavailable."""
    model = get_semantic_model()
    if model is None:
        return None

    embeddings = model.encode([student_answer, *references], normalize_embeddings=True)
    student_embedding = embeddings[0]
    return [float(student_embedding @ ref) for ref in embeddings[1:]]
