import logging
import os
from io import BytesIO
from typing import Dict, Optional, Union

import httpx
from fastapi import APIRouter, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ai_companion.graph import graph_builder
from ai_companion.modules.image import ImageToText
from ai_companion.modules.speech import SpeechToText, TextToSpeech
from ai_companion.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global module instances
speech_to_text = SpeechToText()
text_to_speech = TextToSpeech()
image_to_text = ImageToText()

# Router for WhatsApp
whatsapp_router = APIRouter()

# --- ENHANCED CLIENT CLASS ---
class WhatsAppClient:
    """Handles Blue Ticks, Reactions, and Media Uploads."""
    
    def __init__(self):
        # Support both naming conventions from your previous code
        self.token = os.getenv("WHATSAPP_TOKEN") or os.getenv("WHATSAPP_API_TOKEN")
        self.phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.base_url = f"https://graph.facebook.com/v21.0/{self.phone_id}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def mark_as_read(self, message_id: str):
        """Sends Blue Ticks to the user."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        await self._post("messages", payload)

    async def send_reaction(self, to: str, message_id: str, emoji: str):
        """Reacts to a message (e.g. 👀, 🤔, ✅)."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "reaction",
            "reaction": {
                "message_id": message_id,
                "emoji": emoji
            }
        }
        await self._post("messages", payload)

    async def send_message(self, to: str, content: Union[str, bytes], msg_type: str = "text"):
        """Sends the actual response (Text/Image/Audio)."""
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": msg_type,
        }

        if msg_type == "text":
            payload["text"] = {"body": content}
            await self._post("messages", payload)
        
        elif msg_type in ["audio", "image"]:
            mime_type = "audio/mpeg" if msg_type == "audio" else "image/png"
            media_id = await self._upload_media(content, mime_type)
            
            payload[msg_type] = {"id": media_id}
            await self._post("messages", payload)

    async def download_media(self, media_id: str) -> bytes:
        """Downloads audio or images sent by user."""
        async with httpx.AsyncClient() as client:
            # 1. Get URL
            meta_res = await client.get(f"https://graph.facebook.com/v21.0/{media_id}", headers=self.headers)
            meta_res.raise_for_status()
            download_url = meta_res.json().get("url")
            
            # 2. Download Binary Content
            media_res = await client.get(download_url, headers=self.headers)
            media_res.raise_for_status()
            return media_res.content

    async def _upload_media(self, content: bytes, mime_type: str) -> str:
        """Uploads generated media to WhatsApp."""
        files = {"file": ("media_file", content, mime_type)}
        data = {"messaging_product": "whatsapp", "type": mime_type}
        
        async with httpx.AsyncClient() as client:
            # Note: Do NOT set Content-Type header when uploading files, httpx handles boundaries
            res = await client.post(
                f"{self.base_url}/media",
                headers={"Authorization": self.headers["Authorization"]}, 
                files=files,
                data=data
            )
            res.raise_for_status()
            return res.json()["id"]

    async def _post(self, endpoint: str, json_data: dict):
        async with httpx.AsyncClient() as client:
            res = await client.post(f"{self.base_url}/{endpoint}", headers=self.headers, json=json_data)
            if res.status_code not in [200, 201]:
                logger.error(f"WhatsApp API Error: {res.text}")
            return res

# Initialize Client
wa_client = WhatsAppClient()


# --- ROUTE HANDLERS ---

@whatsapp_router.get("/whatsapp_response", operation_id="whatsapp_verification")
async def whatsapp_verification(request: Request) -> Response:
    """Handles webhook verification handshake."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    # Check both env var names to be safe
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN") or os.getenv("WEBHOOK_VERIFY_TOKEN")
    
    if mode == "subscribe" and token == verify_token:
        logger.info(f"✅ Webhook verified successfully")
        return Response(content=challenge, status_code=200)
    
    logger.warning(f"❌ Verification failed. Got: {token}, Expected: {verify_token}")
    return Response(content="Verification token mismatch", status_code=403)


@whatsapp_router.post("/whatsapp_response", operation_id="whatsapp_message_handler")
async def whatsapp_message_handler(request: Request) -> Response:
    """Main Logic: Reads -> Reacts -> Thinks -> Responds."""
    try:
        data = await request.json()
        logger.info(f"📥 Received webhook data: {data}")
        
        # 1. Validate Payload
        if not data.get("entry") or not data["entry"][0].get("changes"):
            return Response(content="No changes", status_code=200)

        change_value = data["entry"][0]["changes"][0]["value"]
        
        # 2. Ignore Status Updates (Read receipts sent BY us)
        if "statuses" in change_value:
            return Response(content="Status received", status_code=200)

        # 3. Handle User Messages
        if "messages" in change_value:
            message = change_value["messages"][0]
            from_number = message["from"]
            message_id = message["id"]
            session_id = from_number
            
            logger.info(f"📱 Msg from {from_number} | Type: {message['type']}")

            # --- VISUAL FEEDBACK START ---
            # Mark as Read (Blue Ticks)
            await wa_client.mark_as_read(message_id)
            
            # Set Reaction based on input type
            start_reaction = "🤔" # Default thinking
            if message["type"] == "image": start_reaction = "👀" # Looking
            elif message["type"] == "audio": start_reaction = "👂" # Listening
            
            await wa_client.send_reaction(from_number, message_id, start_reaction)
            # --- VISUAL FEEDBACK END ---

            # 4. Extract Content
            content = ""
            if message["type"] == "audio":
                audio_bytes = await wa_client.download_media(message["audio"]["id"])
                content = await speech_to_text.transcribe(audio_bytes)
                logger.info(f"🎤 Transcribed: {content[:30]}...")

            elif message["type"] == "image":
                user_caption = message.get("image", {}).get("caption", "")
                user_question = user_caption if user_caption.strip() else "What is this?"
                
                # Tag for Router to know it's an image
                content = f"[USER_SENT_IMAGE] {user_question}"
                
                image_bytes = await wa_client.download_media(message["image"]["id"])
                
                try:
                    # Vision Model Analysis
                    description = await image_to_text.analyze_image(image_bytes, prompt=user_question)
                    content += f"\n\n[Image Analysis: {description}]"
                    logger.info("✅ Image analyzed")
                except Exception as e:
                    logger.error(f"Vision Error: {e}")
                    content += "\n\n[Image Analysis: Failed to analyze]"

            elif message["type"] == "text":
                content = message["text"]["body"]

            else:
                await wa_client.send_message(from_number, "Sorry, I can't handle this message type yet.")
                return Response(content="Unsupported type", status_code=200)

            # 5. Invoke LangGraph Agent
            logger.info("🚀 Invoking Graph...")
            async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
                graph = graph_builder.compile(checkpointer=short_term_memory)
                
                await graph.ainvoke(
                    {"messages": [HumanMessage(content=content)]},
                    {"configurable": {"thread_id": session_id}},
                )
                
                output_state = await graph.aget_state(config={"configurable": {"thread_id": session_id}})

            # 6. Process Response
            workflow = output_state.values.get("workflow", "conversation")
            response_text = output_state.values["messages"][-1].content
            
            if workflow == "audio":
                audio_buffer = output_state.values["audio_buffer"]
                await wa_client.send_message(from_number, audio_buffer.getvalue(), "audio")
            
            elif workflow == "image":
                image_path = output_state.values["image_path"]
                with open(image_path, "rb") as f:
                    image_data = f.read()
                await wa_client.send_message(from_number, image_data, "image")
                # Send caption separately
                if response_text:
                    await wa_client.send_message(from_number, response_text, "text")
            
            else:
                # Normal Text Response
                await wa_client.send_message(from_number, response_text, "text")

            # 7. Final Reaction (Success)
            await wa_client.send_reaction(from_number, message_id, "✅")

            return Response(content="Processed", status_code=200)

        return Response(content="No messages found", status_code=200)

    except Exception as e:
        logger.exception(f"❌ Error processing webhook: {e}")
        return Response(content="Internal Error", status_code=500)