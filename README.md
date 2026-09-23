# Smart Study AI Companion 🎓
> *"Study smarter. Understand better. Learn faster."*

Smart Study is a complete, full-stack, AI-powered study platform tailored for college students. Students can upload lecture PDFs, textbooks, or course handouts and automatically generate high-yield study summaries, exam-focused important questions, interactive active-recall flashcards, self-grading practice quizzes, grounded AI doubt clarification, and downloadable ReportLab PDF study sheets.

---

## 🚀 Key Features

1. **Multi-Section AI Summary**
   - Automatically analyzes documents and creates 5 structured sections:
     - 1. High-level Overview
     - 2. Core Concepts & Definitions
     - 3. Critical Key Points
     - 4. Exam-Focused High-Yield Points
     - 5. Rapid Revision Checklist Notes
   - One-click copy to clipboard and ReportLab PDF download.

2. **Important Exam Questions & Model Solutions**
   - Generates 5 high-probability university exam questions.
   - Supplies comprehensive answers and professor tips / conceptual explanations.
   - Accordion review interface with copy and export features.

3. **Smart Flashcards (Interactive 3D Active Recall)**
   - 5 high-yield study flashcards with realistic 3D flipping animation.
   - Front: Concept / Question / Category hint.
   - Back: Model Answer / Explanation.
   - Previous, Next, Flip buttons, and keyboard controls (Arrow Left/Right to navigate, Spacebar to flip).

4. **Practice MCQ Quiz**
   - 5 multiple-choice questions with 4 distinct options.
   - Instant visual answer validation: green badges for correct options, red for mistakes.
   - Explanations for every question.
   - Dynamic score tracking (X / 5) with performance feedback and persistent saving to SQLite.

5. **AI Study Assistant (Grounded Document Chat)**
   - Context-aware chatbot powered by Groq API.
   - Retrieves relevant document text chunks using term-frequency and phrase-matching ranking.
   - Clearly flags when a query cannot be answered from the document:
     *"I couldn't find this information in your uploaded material. I can still explain the general concept if you'd like."*
   - Dedicated learning modes:
     - 💬 **Normal Chat**
     - 💡 **Explain Simply** (Beginner-friendly breakdown)
     - 📝 **Summarize** (Concise highlights)
     - 🔍 **Give Example** (Intuitive real-world analogies)
     - ❓ **Ask Me Questions** (5 interactive check-in questions)
     - 🎯 **Exam Answer** (Structured academic format)
   - Persistent chat history in SQLite with clear chat capability.

6. **Publication-Grade PDF Export**
   - Built with ReportLab.
   - Export individual summaries, question sheets, flashcard collections, quizzes, or a combined master study guide.

7. **User Isolation & Authentication**
   - Werkzeug secure password hashing (PBKDF2/SHA256).
   - Session authentication with protected routes.
   - Strict user isolation: users can only view, study, and delete their own files.

8. **Dashboard & History Tracking**
   - Real statistics (Total Materials, Summaries Created, Questions Generated, Quiz Attempts) with zero fake numbers.
   - Visual learning flow roadmap.
   - Full activity timeline with scores, timestamps, and direct study workspace links.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.10+, Flask
- **Database:** SQLite with foreign keys and cascading deletes
- **PDF Extraction:** PyPDF2 (safe page extraction, character normalization, noise removal)
- **AI Engine:** Groq API (`groq` Python SDK) with fast inference models (`qwen/qwen3.8-27b`, `openai/gpt-oss-120b`, Llama series)
- **PDF Generation:** ReportLab
- **Authentication:** Flask Session Auth, Werkzeug security
- **Frontend:** Semantic HTML5, Modern Light-Themed CSS3, Vanilla JavaScript, Jinja2 Templates
- **Production Server:** Gunicorn (Render-ready Procfile included)

---

## 🎨 Design Philosophy: White / Light Aesthetic

Smart Study strictly follows a modern, light, distraction-free design system:
- Crisp white cards with subtle borders (`#E2E8F0`) and soft shadows.
- Vibrant, professional indigo (`#4F46E5`) and emerald (`#10B981`) accents.
- Responsive layout optimized across mobile phones, tablets, laptops, and ultra-wide desktops.
- Fast transitions, keyboard navigation, and accessible UI controls.

---

## 📂 Project Structure

```text
smart-study/
│
├── app.py                     # Main Flask application & routes
├── config.py                  # Environment configuration & constants
├── requirements.txt           # Python package dependencies
├── Procfile                   # Render / Gunicorn deployment entry point
├── README.md                  # Complete documentation
├── .env                       # Local environment variables (gitignored)
├── .env.example               # Template environment configuration
├── .gitignore                 # Git ignore rules
│
├── services/                  # Business logic services
│   ├── __init__.py
│   ├── ai_service.py          # Groq integration, structured JSON parsing, fallback logic
│   ├── pdf_service.py         # PyPDF2 extraction, cleaning, size & format validation
│   ├── document_service.py    # Chunking & keyword context retrieval algorithm
│   └── export_service.py      # ReportLab clean PDF generator
│
├── database/                  # Data layer
│   ├── __init__.py
│   ├── database.py            # SQLite schema initialization & CRUD queries
│   └── smart_study.db         # SQLite database file (gitignored)
│
├── uploads/                   # Stored user PDF uploads (gitignored)
│   └── .gitkeep
│
├── generated_pdfs/            # Temporary generated export files (gitignored)
│   └── .gitkeep
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Layout, navbar, flash alerts, and footer
│   ├── index.html             # Landing page (Hero, Features, How It Works)
│   ├── login.html             # Student login page
│   ├── register.html          # Student registration page
│   ├── dashboard.html         # Stats, drag-and-drop upload, learning flow
│   ├── materials.html         # Document list with delete modal
│   ├── study.html             # Dedicated study workspace (Tabs 1 to 6)
│   ├── history.html           # Activity timeline & quiz results
│   └── profile.html           # Profile settings & password change
│
└── static/                    # Frontend assets
    ├── css/
    │   └── style.css          # Clean modern light CSS design system
    ├── js/
    │   └── app.js             # Drag-drop, flip cards, quiz engine, chat logic
    └── images/                # Static assets & icons
```

---

## ⚙️ Installation & Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/kattubadiyasmin/smart-study.git
cd smart-study
```

### 2. Create and activate a virtual environment
**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root directory (you can copy `.env.example`):
```ini
# Flask Secret Key
SECRET_KEY=smartstudy_super_secret_session_key_2026

# Groq API Key (get your free API key at https://console.groq.com)
GROQ_API_KEY=gsk_your_groq_api_key_here

# Groq Model
GROQ_MODEL=qwen/qwen3.8-27b
```

### 5. Run the application
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000`.

---

## 🚢 Deployment (Render)

Smart Study is configured for seamless deployment on Render:
1. Push your repository to GitHub.
2. In the Render Dashboard, create a new **Web Service**.
3. Connect your `smart-study` GitHub repository.
4. Set the following settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Under **Environment Variables**, add:
   - `SECRET_KEY`: (a long random string)
   - `GROQ_API_KEY`: (your Groq API key)
   - `GROQ_MODEL`: `qwen/qwen3.8-27b`

---

## 🧪 Testing the Complete Workflow

1. **Register & Login:** Create a new student account at `/register`.
2. **Dashboard:** Observe zero state on dashboard metric cards.
3. **Upload PDF:** Drag and drop a course PDF (e.g. computer science or biology chapter).
4. **Summary Module:** Inspect Overview, Key Concepts, Important Points, Exam Points, and Revision Notes. Test copy button.
5. **Questions Module:** Expand questions, review model answers and exam tips.
6. **Flashcards:** Click card or press Spacebar to flip between concept and answer. Navigate with Next/Prev.
7. **MCQ Quiz:** Answer questions, check immediate green/red feedback, review explanations, and view final score (X / 5).
8. **AI Assistant:** Test "Explain Simply", "Give Example", and ask a question not present in the PDF to verify the fallback guardrail.
9. **Export PDF:** Click "Download PDF" on any module or click "Download All Notes PDF" from the header.
10. **Materials & History:** View uploaded documents in "My Materials", verify activity in "History", and test deleting a document.

---

## 📄 License
This project is open-source and available under the MIT License.
