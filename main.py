from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
import json
import re
import pypdf
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="/Users/mahakbansal/Desktop/EVG/session3/document_agent/static"), name="static")

# Mount static files for UI (we will create this directory next)


# Initialize Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-3-flash-preview"

# In-memory storage for documents and history
documents = {}
history = [] # Stores the conversation history for the stateless call

def read_document(doc_id: str) -> str:
    if doc_id not in documents:
        return json.dumps({"error": f"Document {doc_id} not found"})
    return json.dumps({"content": documents[doc_id]["content"]})

def search_document(doc_id: str, query: str) -> str:
    if doc_id not in documents:
        return json.dumps({"error": f"Document {doc_id} not found"})
    content = documents[doc_id]["content"]
    paragraphs = content.split("\n\n")
    if len(paragraphs) <= 1:
        paragraphs = content.split("\n")
        
    results = [p for p in paragraphs if query.lower() in p.lower()]
    return json.dumps({"results": results[:5] if results else "No matches found"})


def get_document_metadata(doc_id: str) -> str:
    if doc_id not in documents:
        return json.dumps({"error": f"Document {doc_id} not found"})
    doc = documents[doc_id]
    return json.dumps({
        "title": doc["title"],
        "type": doc["type"],
        "length": len(doc["content"])
    })

def summarize_document(doc_id: str) -> str:
    if doc_id not in documents:
        return json.dumps({"error": f"Document {doc_id} not found"})
    content = documents[doc_id]["content"]
    
    if "summary" not in documents[doc_id]:
        prompt = f"Summarize the following document content in a few bullet points:\n\n{content[:10000]}"
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            documents[doc_id]["summary"] = response.text
        except Exception as e:
            return json.dumps({"error": f"Failed to generate summary: {str(e)}"})
            
    return json.dumps({"summary": documents[doc_id]["summary"]})

def fetch_url_content(url: str) -> str:
    try:
        if "docs.google.com/spreadsheets" in url:
            import re
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if match:
                file_id = match.group(1)
                url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=csv"
                
        elif "docs.google.com/document" in url:
            import re
            match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if match:
                file_id = match.group(1)
                url = f"https://docs.google.com/document/d/{file_id}/export?format=txt"

                
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)

        soup = BeautifulSoup(response.content, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Try to get main content for Wikipedia or similar sites
        main_contents = soup.find_all(class_="mw-parser-output")
        valid_contents = [c for c in main_contents if len(c.get_text(strip=True)) > 0]
        if valid_contents:
            main_content = max(valid_contents, key=lambda x: len(x.get_text()))
            text = main_content.get_text(separator="\n", strip=True)

        else:
            # Fallback to whole body but remove common noise tags
            for tag in ["nav", "header", "footer", "sidebar"]:
                for element in soup.find_all(tag):
                    element.decompose()
            text = soup.get_text(separator="\n", strip=True)

        
        # Update document content if it exists in session
        for doc_id, data in documents.items():
            if data["title"] == url and data["type"] == "url":
                data["content"] = text
                break
                
        return json.dumps({"content": text[:10000]})
    except Exception as e:
        return json.dumps({"error": f"Failed to fetch URL: {str(e)}"})


tools = {
    "read_document": read_document,
    "search_document": search_document,
    "get_document_metadata": get_document_metadata,
    "summarize_document": summarize_document,
    "fetch_url_content": fetch_url_content,
}


def parse_llm_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError(f"Could not parse: {text}")

def run_agent_loop(user_query: str, max_iterations: int = 5):
    doc_list_str = ""
    for doc_id, data in documents.items():
        doc_list_str += f"- {doc_id}: {data['title']} (Type: {data['type']})\n"
        
    system_prompt = f"""You are a powerful AI Document Analysis Agent. Your job is to help the user analyze, summarize, and compare up to 10 documents.

You have access to the following tools:

1. get_document_metadata(doc_id: str) -> str
   Get metadata like Title, Source, and length of a document.

2. read_document(doc_id: str) -> str
   Read the full text content of a document.

3. search_document(doc_id: str, query: str) -> str
   Find specific information within a document without reading the whole thing.

4. summarize_document(doc_id: str) -> str
   Get a quick summary of a document.

5. fetch_url_content(url: str) -> str
   Fetch the text content of a webpage URL.


Available Documents in this session:
{doc_list_str if doc_list_str else "No documents uploaded yet."}

You must respond in ONE of these two JSON formats:

If you need to use a tool:
{{"tool_name": "<name>", "tool_arguments": {{"<arg_name>": "<value>"}}}}

If you have the final answer:
{{"answer": "<your final answer>"}}

IMPORTANT: 
- Respond with ONLY the JSON. No other text or markdown formatting.
- Use tools whenever you need to access the content of the documents. Do not assume content.
- You are stateless; rely on the history passed in the prompt.
- Provide your final answer in PLAIN TEXT only. Do NOT use markdown formatting like bold (**), italics (*), or lists (-).
- For documents of type 'url', the content in the session might be empty. You MUST use the `fetch_url_content` tool with the URL provided as the title to retrieve the content before you can read or summarize it.
"""


    prompt = system_prompt + "\n\n"
    for msg in history:
        if msg["role"] == "user":
            prompt += f"User: {msg['content']}\n\n"
        elif msg["role"] == "assistant":
            prompt += f"Assistant: {msg['content']}\n\n"
        elif msg["role"] == "tool":
            prompt += f"Tool Result: {msg['content']}\n\n"
            
    prompt += f"User: {user_query}\n\n"
    
    current_turn_history = []
    
    for iteration in range(max_iterations):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            response_text = response.text
        except Exception as e:
            return {"error": f"API Error: {str(e)}"}
            
        try:
            parsed = parse_llm_response(response_text)
        except Exception as e:
            prompt += f"Assistant: {response_text}\n\nUser: Please respond with valid JSON only.\n\n"
            current_turn_history.append({"role": "assistant", "content": response_text})
            current_turn_history.append({"role": "user", "content": "Please respond with valid JSON only."})
            continue
            
        if "answer" in parsed:
            current_turn_history.append({"role": "assistant", "content": response_text})
            log_interaction(user_query, parsed["answer"], current_turn_history)
            history.append({"role": "user", "content": user_query})
            history.append({"role": "assistant", "content": response_text})
            return {"answer": parsed["answer"]}
            
        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = parsed.get("tool_arguments", {})
            
            if tool_name not in tools:
                tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})
            else:
                try:
                    tool_result = tools[tool_name](**tool_args)
                except Exception as e:
                    tool_result = json.dumps({"error": f"Tool execution failed: {str(e)}"})
                    
            prompt += f"Assistant: {response_text}\n\nTool Result: {tool_result}\n\n"
            current_turn_history.append({"role": "assistant", "content": response_text})
            current_turn_history.append({"role": "tool", "content": tool_result})
            
    return {"error": "Max iterations reached"}

def log_interaction(query, answer, turn_history):
    try:
        with open("/Users/mahakbansal/Desktop/EVG/session3/document_agent/interactions.txt", "a") as f:

            f.write(f"User: {query}\n\n")
            for msg in turn_history:
                if msg["role"] == "assistant":
                    f.write(f"LLM: {msg['content']}\n\n")
                elif msg["role"] == "tool":
                    f.write(f"Agent: {msg['content']}\n\n")
            f.write("="*50 + "\n\n")
    except Exception as e:
        print(f"Failed to log interaction: {e}")



@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    import zipfile
    
    if len(documents) >= 10:
        raise HTTPException(status_code=400, detail="Max 10 documents allowed")
        
    filename = file.filename.lower()
    doc_id = f"doc_{len(documents) + 1}"
    text = ""
    doc_type = ""
    
    try:
        if filename.endswith(".pdf"):
            pdf_reader = pypdf.PdfReader(file.file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            doc_type = "pdf"
            
        elif filename.endswith(".docx"):
            with zipfile.ZipFile(file.file) as z:
                xml_content = z.read("word/document.xml")
                soup = BeautifulSoup(xml_content, "html.parser")
                text = soup.get_text(separator="\n", strip=True)
            doc_type = "docx"
            
        elif filename.endswith(".xlsx"):
            with zipfile.ZipFile(file.file) as z:
                if "xl/sharedStrings.xml" in z.namelist():
                    xml_content = z.read("xl/sharedStrings.xml")
                    soup = BeautifulSoup(xml_content, "html.parser")
                    text += soup.get_text(separator="\n", strip=True)
            doc_type = "xlsx"
            
        elif filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            file_bytes = await file.read()
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=file.content_type
                    ),
                    "Extract all text from this image. If it is a diagram, chart, or photo, describe it in detail so that a text-based agent can understand its full content."
                ]
            )
            text = response.text
            doc_type = "image"
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
            
        documents[doc_id] = {
            "title": file.filename,
            "content": text,
            "type": doc_type
        }
        return {"doc_id": doc_id, "title": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/clear")
async def clear_session():
    documents.clear()
    history.clear()
    return {"message": "Session cleared"}


@app.post("/add_link")
async def add_link(url: str = Form(...)):
    if len(documents) >= 10:
        raise HTTPException(status_code=400, detail="Max 10 documents allowed")
        
    doc_id = f"doc_{len(documents) + 1}"
    documents[doc_id] = {
        "title": url,
        "content": "", # Empty content, agent must fetch it
        "type": "url"
    }
    return {"doc_id": doc_id, "title": url}


@app.delete("/document/{doc_id}")
async def delete_document(doc_id: str):
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    del documents[doc_id]
    return {"message": f"Document {doc_id} removed"}

@app.post("/chat")
async def chat(prompt: str = Form(...)):

    result = run_agent_loop(prompt)
    return result

@app.get("/")
async def read_index():
    return FileResponse("/Users/mahakbansal/Desktop/EVG/session3/document_agent/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
