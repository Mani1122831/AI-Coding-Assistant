# 🤖 AI Coding Assistant

A modern, production-quality AI-powered coding tool built with **Python**, **Streamlit**, and the **Google Gemini API**. It helps developers generate, explain, debug, refactor, convert, test, and secure their code — all from a clean, dark-themed developer UI.

---

## 🌟 Features

| Feature | Description |
|---|---|
| ✨ **Generate Code** | Describe requirements in plain English → get production-ready code |
| 🐛 **Debug Code** | Paste buggy code + error message → get a fix with explanation |
| 📖 **Explain Code** | Understand any code snippet with beginner-friendly explanations |
| 🔧 **Refactor Code** | Improve code quality, naming, and structure without changing behavior |
| 🔄 **Convert Code** | Translate code between Python, Java, JavaScript, C++, and more |
| 🧪 **Generate Tests** | Auto-generate pytest, unittest, or Jest-style unit tests |
| 🔐 **Security Analysis** | Scan code for vulnerabilities (injection, hardcoded secrets, etc.) |
| 📁 **Analyze File** | Upload source files (.py, .js, .java, .sql, etc.) for AI analysis |
| 💬 **AI Coding Chat** | Multi-turn chat about code with maintained context |
| ⚙️ **Settings** | View current configuration and setup guidance |

---

## 🏗️ Architecture

```
AI-Coding-Assistant/
│
├── app.py                  ← Streamlit UI & routing (no business logic)
├── requirements.txt        ← Python dependencies
├── .env.example            ← Environment variable template
│
├── config/
│   └── settings.py         ← Pydantic-settings configuration
│
├── models/
│   └── schemas.py          ← Pydantic request/response models
│
├── services/
│   ├── llm_service.py      ← AI provider abstraction + task methods
│   ├── code_service.py     ← Code feature orchestration + validation
│   ├── file_service.py     ← Secure file upload processing
│   └── security_service.py ← Security analysis orchestration
│
├── prompts/
│   ├── generate.py         ← Code generation prompt
│   ├── explain.py          ← Code explanation prompt
│   ├── debug.py            ← Debugging prompt
│   ├── refactor.py         ← Refactoring prompt
│   ├── convert.py          ← Code conversion prompt
│   ├── tests.py            ← Test generation prompt
│   └── security.py         ← Security analysis prompt
│
├── utils/
│   ├── logger.py           ← Centralised logging
│   └── helpers.py          ← Utility functions
│
├── tests/
│   ├── test_helpers.py     ← Helper function tests
│   ├── test_prompts.py     ← Prompt generation tests
│   └── test_services.py    ← Service layer tests (mocked AI)
│
└── data/examples/          ← Sample files for testing
```

### Design Principles

- **Clean separation of concerns** — UI, business logic, AI calls, and prompts are in separate layers
- **Provider abstraction** — `LLMService` wraps `GeminiProvider`; adding OpenAI requires only a new provider class
- **Structured responses** — all AI outputs are parsed into Pydantic models
- **Input validation** — all user inputs are validated before reaching the AI
- **Security first** — API keys never exposed, file uploads strictly validated

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Frontend | Streamlit 1.38+ |
| AI SDK | google-genai 2.3+ |
| AI Model | Gemini 3.8 Flash (configurable) |
| Validation | Pydantic 2 + pydantic-settings |
| Configuration | python-dotenv |
| HTTP | httpx |
| Testing | pytest + pytest-mock |
| Language | Python 3.11+ |

---

## 📦 Installation

### Prerequisites

- Python 3.11 or higher
- pip
- A Gemini API key ([get one free](https://aistudio.google.com/app/apikey))

### Steps

```bash
# 1. Clone the repository (or navigate to the project folder)
git clone <your-repo-url>
cd AI-Coding-Assistant

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Environment Configuration

```bash
# 1. Copy the example environment file
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux

# 2. Open .env and fill in your API key
```

**.env file:**

```env
AI_PROVIDER=gemini
GEMINI_MODEL=gemini-flash-latest
GEMINI_API_KEY=your_actual_api_key_here
MAX_FILE_SIZE_MB=2
LOG_LEVEL=INFO
```

### Configuration Options

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `gemini` | LLM provider (currently: `gemini`) |
| `GEMINI_MODEL` | `gemini-flash-latest` | Model identifier (alias: `AI_MODEL`) |
| `GEMINI_API_KEY` | *(required)* | Your Gemini API key |
| `MAX_FILE_SIZE_MB` | `2` | Max upload file size (1–10 MB) |
| `LOG_LEVEL` | `INFO` | Logging level |

### Supported Models

| Model | Description |
|---|---|
| `gemini-flash-latest` | Default & recommended — fast, balanced, resilient |
| `gemini-3.5-flash-lite` | Fastest, lowest cost |
| `gemini-3.8-flash` | Advanced multimodal & coding |
| `gemini-3.1-pro-preview` | Most capable, complex reasoning |

---

## ▶️ Running Locally

```bash
# Make sure your .venv is activated and .env is configured
streamlit run app.py
```

The app will open at **http://localhost:8501** in your browser.

---

## 🧪 Testing

```bash
# Run all tests (no API key required — AI is mocked)
pytest

# Verbose output
pytest -v

# Run specific test file
pytest tests/test_helpers.py -v
pytest tests/test_prompts.py -v
pytest tests/test_services.py -v

# Run with coverage (install pytest-cov first)
pip install pytest-cov
pytest --cov=. --cov-report=term-missing
```

Tests cover:
- ✅ All helper utility functions
- ✅ All prompt generation functions
- ✅ Service layer validation logic
- ✅ File upload validation (size, type, encoding)
- ✅ Error handling and AI error classification
- ✅ Input validation edge cases

---

## 📸 Screenshots

> *Add screenshots here after running the application.*

| Dashboard | Code Generation |
|---|---|
| *(screenshot)* | *(screenshot)* |

| Security Analysis | AI Chat |
|---|---|
| *(screenshot)* | *(screenshot)* |

---

## 🔐 Security Considerations

- **API keys**: Stored only in `.env` (excluded from git via `.gitignore`). Never hardcoded.
- **File uploads**: Validated by extension whitelist, size limit, and text-only decoding. Never executed.
- **User code**: Treated as untrusted text. Never executed on the host machine.
- **No code execution**: There is deliberately no "Run Code" button. Execution requires a properly sandboxed environment.
- **Error messages**: Technical details are logged server-side only. Users see friendly messages.
- **Security analysis**: Advisory only — clearly labelled. Not a guarantee of security.

---

## 🔮 Future Roadmap

### V2 — Knowledge & Context
- RAG-based documentation search
- Embeddings + vector database
- Project-wide code understanding

### V3 — Autonomous Agent
- Multi-file editing
- GitHub repository analysis
- Automatic test execution
- Code review agent

### V4 — Full Workspace
- Isolated code execution sandbox
- Multi-agent architecture
- Project memory
- Deployment automation

---

## 🚀 GitHub Setup

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Initial commit
git commit -m "feat: initial AI Coding Assistant implementation"

# Create repository on GitHub, then:
git remote add origin https://github.com/your-username/ai-coding-assistant.git
git branch -M main
git push -u origin main
```

> ⚠️ **Important**: Never commit `.env`. The `.gitignore` already excludes it.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with ❤️ using Python, Streamlit, and Google Gemini*
