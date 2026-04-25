# Agentic Document Analyst

A powerful, AI-driven document analysis web application powered by **Gemini 3** and **FastAPI**. This application allows users to upload various document formats or provide links to reason over content, extract information, and generate summaries using an autonomous agentic loop.

## 🚀 Features

- **Multi-Format Document Support**: Upload and analyze PDFs, Word documents (`.docx`), Excel sheets (`.xlsx`), and Images (`.png`, `.jpg`, `.jpeg`, `.webp`).
- **Intelligent URL Scraping**: Automatically fetches and cleans content from standard URLs.
- **Google Docs & Sheets Integration**: Automatically detects and rewrites Google Docs and Sheets URLs to export public content as plain text or CSV for seamless processing.
- **Autonomous Agentic Loop**: The backend agent can autonomously decide to call tools like `fetch_url_content`, `search_document`, or `summarize_document` to answer user queries.
- **Premium UI Experience**: 
  - Sleek glassmorphic design.
  - Custom AI-generated favicon.
  - "Copy" button for all agent responses.
  - "Start Afresh" button to clear session state and history.

## 🛠️ Tech Stack

- **Backend**: Python 3.9+, FastAPI, Uvicorn
- **AI**: Google GenAI SDK (Gemini 3)
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism), JavaScript

## ⚙️ Setup & Installation

1. **Clone the repository** (or navigate to the project directory).
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Configuration**:
   Create a `.env` file in the root directory and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```
4. **Run the Application**:
   ```bash
   python main.py
   ```
   The server will start at `http://0.0.0.0:8000`.

## 📝 License

MIT
