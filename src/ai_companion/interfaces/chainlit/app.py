from io import BytesIO
import logging

import chainlit as cl
from langchain_core.messages import AIMessageChunk, HumanMessage
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


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session"""
    thread_id = cl.user_session.get("id")
    cl.user_session.set("thread_id", thread_id)
    
    logger.info(f"🆔 New Chainlit session started with thread_id: {thread_id}")
    logger.info(f"📊 Short-term memory DB: {settings.SHORT_TERM_MEMORY_DB_PATH}")
    
    # Updated Name to Muzzamil
    await cl.Message(
        content=f"👋 Hey! I'm Muzzamil. Ready to chat!\n\n*Session: {thread_id[:8]}...*"
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle text messages and images"""
    thread_id = cl.user_session.get("thread_id")
    logger.info(f"📨 [Chainlit] Processing message for thread {thread_id}: '{message.content[:50]}...'")
    
    msg = cl.Message(content="")

    # Process any attached images
    content = message.content
    if message.elements:
        for elem in message.elements:
            if isinstance(elem, cl.Image):
                # 1. Define user question or default
                user_question = content if content.strip() else "Please describe what you see in this image."
                
                # 2. CRITICAL: Add the [USER_SENT_IMAGE] tag for the Router
                content = f"[USER_SENT_IMAGE] {user_question}"
                
                logger.info(f"🖼️ Processing attached image with question: '{user_question[:50]}...'")
                with open(elem.path, "rb") as f:
                    image_bytes = f.read()

                try:
                    # 3. Analyze image
                    description = await image_to_text.analyze_image(
                        image_bytes,
                        prompt=user_question if user_question.strip() else "Please describe what you see in this image in detail."
                    )
                    # 4. CRITICAL: Add the [Image Analysis] tag for the Character Prompt
                    content += f"\n\n[Image Analysis: {description}]"
                    logger.info(f"✅ Image analyzed: {description[:100]}...")
                except Exception as e:
                    logger.error(f"❌ Failed to analyze image: {e}")
                    content += "\n\n[Image Analysis: Failed to analyze the image]"

    # Process through graph
    async with cl.Step(type="run", name="Processing"):
        logger.info(f"🚀 [Chainlit] Invoking graph for thread {thread_id}")
        logger.info(f"📂 Using DB: {settings.SHORT_TERM_MEMORY_DB_PATH}")
        
        async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
            graph = graph_builder.compile(checkpointer=short_term_memory)
            
            async for chunk in graph.astream(
                {"messages": [HumanMessage(content=content)]},
                {"configurable": {"thread_id": thread_id}},
                stream_mode="messages",
            ):
                if chunk[1]["langgraph_node"] == "conversation_node" and isinstance(chunk[0], AIMessageChunk):
                    await msg.stream_token(chunk[0].content)

            output_state = await graph.aget_state(config={"configurable": {"thread_id": thread_id}})
            logger.info(f"✅ [Chainlit] Graph execution completed. Workflow: {output_state.values.get('workflow')}")

    # Handle different response types
    workflow = output_state.values.get("workflow")
    
    if workflow == "audio":
        logger.info(f"🔊 Sending audio response")
        response = output_state.values["messages"][-1].content
        audio_buffer = output_state.values["audio_buffer"]
        output_audio_el = cl.Audio(
            name="Audio",
            auto_play=True,
            mime="audio/mpeg3",
            content=audio_buffer,
        )
        await cl.Message(content=response, elements=[output_audio_el]).send()
    elif workflow == "image":
        logger.info(f"🖼️ Sending image response")
        response = output_state.values["messages"][-1].content
        image = cl.Image(path=output_state.values["image_path"], display="inline")
        await cl.Message(content=response, elements=[image]).send()
    else:
        logger.info(f"💬 Sending text response")
        await msg.send()


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.AudioChunk):
    """Handle incoming audio chunks"""
    if chunk.isStart:
        buffer = BytesIO()
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)
        logger.info(f"🎤 Started receiving audio")
    cl.user_session.get("audio_buffer").write(chunk.data)


@cl.on_audio_end
async def on_audio_end(elements):
    """Process completed audio input"""
    thread_id = cl.user_session.get("thread_id")
    logger.info(f"🎤 [Chainlit] Audio recording ended for thread {thread_id}")
    
    audio_buffer = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)
    audio_data = audio_buffer.read()

    input_audio_el = cl.Audio(mime="audio/mpeg3", content=audio_data)
    await cl.Message(author="You", content="", elements=[input_audio_el, *elements]).send()

    logger.info(f"🔄 Transcribing audio...")
    transcription = await speech_to_text.transcribe(audio_data)
    logger.info(f"📝 Transcription: {transcription[:50]}...")

    logger.info(f"🚀 [Chainlit] Processing audio transcription through graph")
    async with AsyncSqliteSaver.from_conn_string(settings.SHORT_TERM_MEMORY_DB_PATH) as short_term_memory:
        graph = graph_builder.compile(checkpointer=short_term_memory)
        output_state = await graph.ainvoke(
            {"messages": [HumanMessage(content=transcription)]},
            {"configurable": {"thread_id": thread_id}},
        )

    logger.info(f"🔊 Synthesizing speech response...")
    audio_buffer = await text_to_speech.synthesize(output_state["messages"][-1].content)

    output_audio_el = cl.Audio(
        name="Audio",
        auto_play=True,
        mime="audio/mpeg3",
        content=audio_buffer,
    )
    await cl.Message(content=output_state["messages"][-1].content, elements=[output_audio_el]).send()
    logger.info(f"✅ [Chainlit] Audio response sent")