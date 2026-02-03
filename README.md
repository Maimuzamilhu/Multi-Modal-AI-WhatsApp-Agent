# 🤖 Muzz - The Ultimate AI WhatsApp Companion

![Muzz AI Logo](muzz_ai_logo_1770145627798.png)

> **"Your intelligent, multi-modal companion that lives right in WhatsApp."**

Muzz is a cutting-edge AI agent designed to interact with you seamlessly through WhatsApp. It's not just a chatbot; it's a persistent companion with long-term memory, vision, voice capabilities, and awareness of its own schedule.

---

## 🚀 Key Features

*   **🧠 Long-Term Memory**: Remembers your conversations, preferences, and facts using **Qdrant** vector database. Note: "User loves cricket? Muzz remembers."
*   **👁️ Vision**: Send images to Muzz, and it will analyze and discuss them with you (powered by Llama 3.2 11B Vision).
*   **🗣️ Voice & Speech**:
    *   **Speaks**: Responds with ultra-realistic voice notes using **ElevenLabs**.
    *   **Listens**: Transcribes your voice notes using **Groq Whisper**.
*   **📅 Schedule Awareness**: Muzz knows what day/time it is and can have its own routine (e.g., "I'm at the gym right now").
*   **🎨 Image Generation**: Can generate images on demand (using Flux/Pollinations).
*   **🔗 Multi-Interface**:
    *   **WhatsApp**: The primary interface for daily use.
    *   **Chainlit**: A web-based UI for debugging, memory inspection, and testing.

---

## 🛠️ Tech Stack

Muzz is built with a modern, high-performance stack:

| Component | Technology | Usage |
| :--- | :--- | :--- |
| **Orchestration** | **LangGraph** | Manages the agent's state, memory, and complex workflows. |
| **LLM Brain** | **Llama 3.3 / 3.1** | Running on **Groq** for lightning-fast inference. |
| **Backend** | **FastAPI** | Handles webhooks from WhatsApp and API requests. |
| **Database** | **Supabase** (Postgres) | Stores memory logs and structured data. |
| **Vector DB** | **Qdrant** | Semantic search for long-term memory retrieval. |
| **Voice** | **ElevenLabs** | Text-to-Speech (TTS) for voice notes. |
| **Transcription**| **Whisper (Groq)** | Speech-to-Text (STT) for processing your content. |

---

## 📂 Project Structure

```
├── src/ai_companion/
│   ├── core/           # Prompts, Configuration
│   ├── graph/          # LangGraph Nodes, State, & Graph Logic
│   ├── interfaces/     # WhatsApp Webhook & Chainlit App
│   └── modules/        # Capabilities (Vision, Memory, Speech, Image)
├── Dockerfile          # For the WhatsApp/FastAPI Service
├── Dockerfile.chainlit # For the Chainlit UI Service
├── docker-compose.yml  # Run everything together
```

---

## ⚡ Getting Started

### Prerequisites

*   **Docker & Docker Compose**
*   **Python 3.12+** (if running locally without Docker)
*   **API Keys**:
    *   Groq API Key
    *   ElevenLabs API Key
    *   Qdrant API Key & URL
    *   WhatsApp Business API Credentials (Meta Developer)

### 1. Clone & Configure

1.  Clone this repository.
2.  Copy the example env file:
    ```bash
    cp .env.example .env
    ```
3.  Fill in your keys in `.env`.

### 2. Run with Docker (Recommended)

Start the entire system (Chainlit UI + WhatsApp Endpoint):

```bash
docker-compose up -d --build
```

### 3. Expose to WhatsApp

To receive messages from WhatsApp, your local server needs to be accessible from the internet.

1.  **Using Ngrok**:
    ```bash
    ngrok http 8080
    ```
2.  Copy the forwarding URL (e.g., `https://abc-123.ngrok-free.app`).
3.  Go to your **Meta Developer App > WhatsApp > Configuration**.
4.  Set the **Callback URL** to: `https://your-ngrok-url/webhook`
5.  Verify the token (should match `WHATSAPP_VERIFY_TOKEN` in your `.env`).

---

## 🧪 Testing

### Option A: Chainlit UI (Debug Mode)
Open `http://localhost:8000` in your browser.
*   Chat with Muzz directly.
*   See the "Chain of Thought" (LangGraph steps) in real-time.
*   Inspect memories and tool calls.

### Option B: WhatsApp (Production Mode)
Send a message to your test number.
*   **Text**: "Hey Muzz, who are you?"
*   **Voice**: Send a voice note.
*   **Image**: Send a photo and ask "What do you see?"

---

## 🧹 Cleaning Up

Stop all containers:
```bash
docker-compose down
```

---

*Built with ❤️.*
