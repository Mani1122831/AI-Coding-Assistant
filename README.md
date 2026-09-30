# 🤖 AI Coding Assistant

A modern, production-grade AI-powered software engineering workspace built with **Python 3.11+**, **Streamlit**, **MongoDB Atlas**, and the **Google Gemini API** (`google-genai` SDK). It provides developers with full-lifecycle coding assistance — code generation, debugging, explanation, refactoring, cross-language conversion, test synthesis, security vulnerability auditing, file analysis, persistent user history with secret redaction, user authentication, and profile management.

---

## 🌟 Key Features

| Category | Feature | Description |
|---|---|---|
| 🔐 **Security & Auth** | **User Authentication** | Secure Login & Registration with deterministic redirect to login, bcrypt hashing, and password complexity rules |
| 🔑 **Security & Auth** | **Forgot & Reset Password** | Single-use cryptographically secure SHA-256 tokens, configurable SMTP email delivery, and enumeration prevention |
| 👤 **Account** | **User Profile** | Edit profile info, change passwords with current-password verification, and view activity audit logs |
| 📜 **Persistence** | **Coding History** | User-isolated coding interactions saved to MongoDB with automated secret/credential redaction |
| ✨ **AI Coding** | **Generate Code** | Translate natural-language requirements into clean, idiomatic code with dependency lists |
| 🐛 **AI Coding** | **Debug Code** | Analyze bugs and stack traces, diagnose root causes, and provide verified corrected code |
| 📖 **AI Coding** | **Explain Code** | Deconstruct complex code into plain-English summaries, line-by-line analyses, and concept breakdowns |
| 🔧 **AI Coding** | **Refactor Code** | Improve readability, modularity, and performance with itemized issues and remediations |
| 🔄 **AI Coding** | **Convert Code** | Translate code between languages (Python, Java, TypeScript, C++, Go, Rust, etc.) |
| 🧪 **AI Coding** | **Generate Tests** | Synthesize comprehensive unit test suites using pytest, unittest, or Jest |
| 🛡️ **Security** | **Security Analysis** | Scan code for vulnerabilities (injection, hardcoded secrets, CSRF, insecure deserialization) |
| 📁 **Workspace** | **Analyze File** | Upload and analyze source code files (.py, .js, .java, .cpp, .sql, etc.) |
| 💬 **AI Assistant** | **AI Coding Chat** | Multi-turn conversational coding companion with contextual awareness |
| ⚙️ **Operations** | **Settings & Health** | Live MongoDB connection test, Gemini API connectivity verification, and model selection |

---

## 🏗️ Architecture & Project Structure

```
AI-Coding-Assistant/
│
├── app.py                      ← Streamlit UI, routing, session management, and auth guards
├── requirements.txt            ← Project dependencies (pinned and validated)
├── .env.example                ← Environment variable template
├── .gitignore                  ← Git exclusion rules (.env, __pycache__, logs)
├── README.md                   ← Project documentation
├── pytest.ini                  ← Pytest configuration
│
├── config/
│   ├── __init__.py
│   └── settings.py             ← Pydantic-settings configuration for Gemini and MongoDB
│
├── models/
│   ├── __init__.py
│   └── schemas.py              ← Pydantic schemas (Auth, History, Activity, AI Tasks)
│
├── services/
│   ├── __init__.py
│   ├── mongo_service.py        ← MongoDB client singleton, connection lifecycle, and index management
│   ├── auth_service.py         ← Bcrypt password hashing, policy verification, user accounts, password resets
│   ├── email_service.py        ← Configurable SMTP email delivery for single-use password reset links
│   ├── history_service.py      ← User history persistence, secret redaction, isolation queries
│   ├── activity_service.py     ← Lightweight audit logging for user events
│   ├── llm_service.py          ← LLM provider abstraction and Gemini SDK integration
│   ├── code_service.py         ← Code generation, debugging, refactoring orchestration
│   ├── file_service.py         ← Safe file upload handling and size/type validation
│   └── security_service.py     ← Security vulnerability auditing
│
├── prompts/
│   ├── __init__.py
│   ├── generate.py             ← Code generation prompt templates
│   ├── explain.py              ← Code explanation prompt templates
│   ├── debug.py                ← Debugging prompt templates
│   ├── refactor.py             ← Refactoring prompt templates
│   ├── convert.py              ← Code conversion prompt templates
│   ├── tests.py                ← Test generation prompt templates
│   └── security.py             ← Security analysis prompt templates
│
├── utils/
│   ├── __init__.py
│   ├── logger.py               ← Structured application logging
│   └── helpers.py              ← Sanitization, markdown cleaning, file formatting helpers
│
└── tests/
    ├── __init__.py
    ├── test_helpers.py         ← 35+ unit tests for utility functions
    ├── test_prompts.py         ← 28+ unit tests for prompt formatting
    ├── test_services.py        ← 35+ unit tests for AI and file services
    ├── test_auth.py            ← 35+ unit tests for auth, bcrypt, password reset, and tokens
    ├── test_history_activity.py← 17+ unit tests for secret redaction, history, and activity
    └── test_e2e_auth_flow.py   ← End-to-end integration test for registration, login, logout, and password resets
```

---

## 🛠️ Technology Stack

| Layer | Component | Description |
|---|---|---|
| **Frontend** | Streamlit 1.38+ | Modern dark-themed responsive developer interface |
| **Persistence** | MongoDB Atlas / PyMongo 4.6+ | Distributed NoSQL database for users, history, and activity logs |
| **Authentication** | Bcrypt 4.1+ | Salted password hashing with 12 rounds of key derivation |
| **Validation** | Pydantic 2.8+ / Email-Validator | Type-safe schema validation and input sanitization |
| **AI SDK** | Google GenAI SDK (`google-genai`) | Official Gemini SDK supporting flash and pro model variants |
| **Testing** | Pytest + Pytest-Mock | 152+ automated unit & integration tests with 100% pass rate |
| **Runtime** | Python 3.11 / 3.12 / 3.13 | Cross-platform compatibility |

---

## 📦 Installation & Setup

### 1. Clone & Setup Virtual Environment

```bash
# Clone the repository
git clone <repository-url>
cd AI-Coding-Assistant

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure your credentials:

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env`:

```env
# AI Provider & Model Configuration
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-flash-latest
GEMINI_API_KEY=your_gemini_api_key_here

# MongoDB Atlas Database Configuration
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=ai_coding_assistant
MONGODB_USERS_COLLECTION=users
MONGODB_HISTORY_COLLECTION=coding_history
MONGODB_ACTIVITY_COLLECTION=activity_logs

# Application Constraints
MAX_FILE_SIZE_MB=2
LOG_LEVEL=INFO
```

> 🔒 **Security Notice**:
> - Never commit your `.env` file. It is automatically excluded via `.gitignore`.
> - All detected API keys and passwords in user code are automatically sanitized with `[REDACTED_SECRET]` before saving to MongoDB history.

---

## ▶️ Running the Application

Launch the Streamlit web application:

```bash
streamlit run app.py
```

Open your browser at **http://localhost:8501**.

### User Workflow:
1. **Register**: Create an account with your Name, Username, Email, and a strong password (minimum 8 characters with uppercase, lowercase, digit, and special symbol).
2. **Login**: Authenticate securely using your Email or Username and Password.
3. **Workspace**: Access the protected AI coding tools from the sidebar.
4. **History**: Re-open previous code generations, search keywords, or filter by operation type.
5. **Profile**: Update your display name/username, change password, or review your activity audit log.
6. **Settings**: Run live health checks on your MongoDB connection and Gemini API.

---

## 🧪 Running Unit Tests

The test suite runs completely offline with mocked AI and database layers — no API key or live database required.

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_history_activity.py -v
python -m pytest tests/test_services.py -v
python -m pytest tests/test_prompts.py -v
python -m pytest tests/test_helpers.py -v
```

### Test Coverage Highlights:
- **135 total unit tests**: 100% passing.
- **Authentication**: Salt generation, bcrypt verification, password policy enforcement, unique constraints, error handling.
- **History & Secret Redaction**: Google/Gemini keys, OpenAI keys, GitHub PATs, AWS access keys, MongoDB URIs, and database connection strings.
- **AI Services**: Request validation, error mapping (auth, rate limits, timeouts), and prompt construction.

---

## 🔒 Security Best Practices Implemented

- **Password Security**: Passwords hashed with bcrypt (12 rounds) and never stored or logged in plaintext.
- **Session Protection**: All AI routes are guarded behind authenticated session state. Unauthenticated users are redirected to the Login/Register screen.
- **Secret Redaction**: Regex-based credential sanitizer scrubs API keys, database connection strings, and tokens from saved coding history.
- **User Isolation**: All database queries for history and activities strictly filter on the authenticated `user_id`.
- **Safe File Uploads**: Uploaded files undergo MIME/extension whitelisting, size caps (2MB default), path traversal protection, and text-only decoding.
- **Advisory Security Analysis**: Security analysis scans check for OWASP Top 10 vulnerabilities and provide remediation advice.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
