# AI Resume Builder & Cover Letter Generator

An advanced, full-stack application that leverages LangGraph and Sarvam AI to dynamically tailor your Resume to any given Job Description, while seamlessly generating a production-ready, ATS-friendly Cover Letter (`.docx`) in seconds. 

## Features
- **Dynamic AI Suggestions**: Upload any PDF Resume and paste a Job Description. The integrated LangGraph orchestration evaluates semantic gaps and automatically generates JSON-based diffs with exact replacement suggestions to better align your resume to the target role.
- **Instant Cover Letters**: Optionally provide a Target Company and Hiring Manager name. The backend will autonomously author a powerful 200-word cover letter focusing on quantifiable metrics.
- **Native Document Generation**: Automatically builds a flawlessly formatted MS Word (`.docx`) file locally, avoiding external generation artifacts and allowing instant downloads seamlessly through the UI.
- **Fully Local Architecture**: A cleanly separated Next.js Frontend with an asynchronous FastAPI backend.

---

## 🚀 Tech Stack
### Frontend
- **Framework**: Next.js (React)
- **Styling**: Tailwind CSS
- **Network**: Fetch API

### Backend 
- **Framework**: FastAPI (Python)
- **AI Orchestration**: LangGraph
- **LLM Engine**: Sarvam AI (`sarvam-30b`)
- **PDF Parsing**: Docling
- **Doc Generation**: `python-docx`

---

## ⚙️ Setup & Installation

### 1. Clone the Repository
```bash
git clone <your-repo-link>
cd resume-parser
```

### 2. Backend Setup
The backend runs on Python and FastAPI.
```bash
cd backend
python -m venv .venv

# Activate the virtual environment:
# On Windows:
.\.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Environment Setup
cp .env.example .env
# Open .env and add your SARVAM_API_KEY
```

### 3. Frontend Setup
The frontend is a modern Next.js application.
```bash
cd frontend

# Install Node dependencies
npm install

# Environment Setup
cp .env.example .env
# (Optional) adjust NEXT_PUBLIC_API_URL if needed
```

---

## 🏃‍♂️ Running the Application

To run the application locally, you will need to start both servers.

1. **Start the Backend:**
   Ensure your virtual environment is activated.
   ```bash
   cd backend
   python main.py
   ```
   *The backend will boot up via Uvicorn on `http://0.0.0.0:8000`.*

2. **Start the Frontend:**
   ```bash
   cd frontend
   npm run dev
   ```
   *The frontend will launch at `http://localhost:3000`.*

3. **Access the App:** Open your browser and navigate to `http://localhost:3000` to start automatically analyzing your resume!
