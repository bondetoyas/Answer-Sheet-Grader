# Automated Answer Sheet Grader 🎓

An AI-assisted web application that helps teachers evaluate short subjective answers. It extracts typed text from answer-sheet images, grades it against a teacher-defined rubric, and lets the teacher review and save the final score.

> 👩‍🏫 **Teacher-in-control:** the system suggests a grade, but the teacher approves or overrides it.

## 🚀 Overview

Manual answer-sheet evaluation takes time. This project provides a local workflow where a teacher uploads a typed answer-sheet image, checks the OCR result, applies a rubric, and stores the reviewed final score.

## ✨ Features

- 📄 Upload typed English answer-sheet images (`.png`, `.jpg`, or `.jpeg`)
- 🖼️ Preview the original answer sheet beside editable OCR text
- 🔎 Improve images before OCR with rotation correction, contrast, sharpening, resizing, and thresholding
- 🔤 Extract text locally with Tesseract OCR
- 📋 Create a custom rubric with key points and marks
- 🤖 Generate an AI-suggested score with a point-by-point rubric breakdown
- ✏️ Let teachers adjust and approve the final score
- 💾 Save submissions, rubric data, scores, and image paths in SQLite
- 📊 Load saved records and reopen original uploaded scans
- ✂️ Detect several answers on one sheet (`Q1.`, `2)`, `Ans 3:` markers) and pick which one to grade
- 🔐 Teacher login, password change, and an admin page to add teachers and reset passwords
- 🔄 Connect React frontend and FastAPI backend through REST APIs

## 🏗️ Application Architecture

```text
             Teacher
                │
                ▼
        React Frontend
        localhost:5173
                │
          HTTP / REST API
                │
                ▼
         FastAPI Backend
        127.0.0.1:8000
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
 Image      OCR Engine   Rubric
 Upload     Tesseract    Grader
     │          │          │
     └──────────┴──────────┘
                │
                ▼
        SQLite Database
                │
                ▼
   Final Score + Teacher Review
```

## 🛠️ Technologies Used

### Frontend

- React 19 + Vite
- Tailwind CSS v4 (`@tailwindcss/vite` plugin, utility classes in the components)
- JavaScript (JSX)

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn

### OCR, Database, and Image Processing

- Tesseract OCR
- pytesseract
- Pillow
- SQLite

### Development Tools

- Git and GitHub
- npm
- Python virtual environments

## 📁 Project Structure

```text
Automated Answer Sheet Grader/
│
├── frontend/                  # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx            # Login / dashboard switch
│   │   ├── index.css          # Tailwind entry (@import "tailwindcss")
│   │   ├── components/        # Login, Dashboard, GradeForm, History, AccountPanel, ui
│   │   └── lib/               # api.js (auth + fetch), rubric.js (rubric parser)
│   ├── package.json
│   └── vite.config.js
│
├── backend/                   # FastAPI backend
│   ├── main.py                # OCR, grading, SQLite, and API logic
│   ├── requirements.txt
│   ├── grader.db              # Created automatically
│   └── uploads/               # Uploaded answer-sheet images
│
├── .gitignore
└── README.md
```

## ⚙️ Installation

### 1. Install prerequisites

Install Python 3.11+, Node.js LTS, and Tesseract OCR.

On Windows, install Tesseract with:

```powershell
winget install -e --id UB-Mannheim.TesseractOCR
```

Verify the installation:

```powershell
& "C:\Program Files\Tesseract-OCR\tesseract.exe" --version
```

### 2. Frontend setup 🎨

```powershell
cd "C:\Automated Answer Sheet Grader\frontend"
npm install        # also installs Tailwind CSS
npm run dev
```

The frontend normally runs at:

```text
http://localhost:5173
```

### 3. Backend setup 🐍

Open another terminal:

```powershell
cd "C:\Automated Answer Sheet Grader\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# optional paraphrase matching: python -m pip install -r requirements-semantic.txt
python -m uvicorn main:app --reload
```

The backend normally runs at:

```text
http://127.0.0.1:8000
```

FastAPI interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

## 📋 Rubric Format

Enter one rubric item per line:

```text
Rubric point | matching keywords | expected meaning | marks
```

The "expected meaning" is a short sentence used for semantic (SBERT) matching; the 3-field form `Point | keywords | marks` is also accepted (keyword-only for that line).

```text
Uses sunlight | sunlight | Plants use sunlight for photosynthesis. | 1
Uses water | water | Plants need water during photosynthesis. | 1
Uses carbon dioxide | carbon dioxide, carbon | Plants use carbon dioxide from air. | 1
Produces glucose or food | glucose, food | Plants make glucose or food. | 1
Releases oxygen | oxygen | Oxygen is released during photosynthesis. | 1
```

A point is awarded if a keyword/phrase appears as a whole word in the answer **or** the answer's SBERT similarity to the expected meaning is ≥ 0.60. If `sentence-transformers` or its model can't be loaded, grading falls back to keywords only and the UI says so.

## ⚙️ Configuration

| Variable | Where | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | backend | `production` makes `SECRET_KEY` mandatory |
| `SECRET_KEY` | backend | Signs login tokens (required in production) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | backend | Creates the first teacher account on startup |
| `DATA_DIR` | backend | Where `grader.db` and `uploads/` live |
| `TESSERACT_CMD` | backend | Path to the Tesseract binary (not needed on PATH / default Windows install) |
| `CORS_ORIGINS` | backend | Comma-separated allowed frontend origins |
| `VITE_API_URL` | frontend | Backend URL (default `http://127.0.0.1:8000`) |

On Linux/macOS install Tesseract with `sudo apt install tesseract-ocr` / `brew install tesseract`.

## 🔐 Accounts & Production Deployment

All endpoints except `/`, `/health` and `/auth/login` need a login. Each teacher only sees their own submissions and scans. Admins can add teachers and reset passwords from the Account section of the app (or use `python manage.py create-user <name> [--admin]`). The account created from `ADMIN_USERNAME` is an admin.

```bash
cp .env.example .env     # set SECRET_KEY and ADMIN_PASSWORD
docker compose up --build   # app on http://localhost:8080
```

Add `WITH_SEMANTIC=true` to `.env` to include SBERT matching in the image. Put a TLS-terminating reverse proxy (Caddy, nginx, a cloud load balancer) in front, and back up the `grader-data` volume. Run a single backend worker (SQLite, in-memory login limiter).

## 🧪 Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests      # or: python -m unittest discover -s tests
```

## 📡 API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Check whether the backend is running |
| `POST` | `/ocr` | Upload a typed image and extract text |
| `POST` | `/auth/login`, `/auth/change-password` | Log in / change own password |
| `GET/POST` | `/admin/users`, `/admin/users/{id}/reset-password` | Admin only: list, add, reset |
| `POST` | `/grade` | Grade text against a rubric |
| `POST` | `/submissions` | Save a teacher-reviewed submission |
| `GET` | `/submissions` | Load saved submissions |
| `PUT` | `/submissions/{id}` | Edit a saved score / names / answer |
| `DELETE` | `/submissions/{id}` | Delete a saved record (and its scan) |
| `GET` | `/uploads/{filename}` | Open an uploaded answer-sheet image |

## 🔄 Current Workflow

```text
Upload typed answer-sheet image
        ↓
Image preprocessing + Tesseract OCR
        ↓
Teacher corrects OCR text if needed
        ↓
Rubric-based scoring
        ↓
Teacher approves or overrides score
        ↓
SQLite saves the complete record
```

## ⚠️ Current Limitations

- OCR is currently intended for typed English text. Question splitting relies on markers such as `Q1.` / `2)` being read correctly.
- Handwriting recognition is not included yet.
- Keyword matching can miss correct answers written using different words.
- Single-node SQLite deployment; for multiple servers move to PostgreSQL.
- Scans are stored on local disk (`DATA_DIR`).

## 🔮 Future Improvements

2. 🧠 SBERT semantic similarity for paraphrased answers
3. ✍️ Handwriting OCR with TrOCR
4. 👥 Student records (a students table instead of free-text names)
5. 📈 Class performance and question analytics
6. 🐘 PostgreSQL for multi-user deployment
7. ☁️ Deployment, tests, and project documentation
