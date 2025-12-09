import logging
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from ai_companion.core.prompts import MEMORY_ANALYSIS_PROMPT
from ai_companion.modules.memory.long_term.vector_store import get_vector_store
from ai_companion.settings import settings
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryAnalysis(BaseModel):
    """Result of analyzing a message for memory-worthy content."""

    is_important: bool = Field(
        ...,
        description="Whether the message is important enough to be stored as a memory",
    )
    formatted_memory: Optional[str] = Field(..., description="The formatted memory to be stored")


class MemoryManager:
    """Manager class for handling long-term memory operations."""

    def __init__(self) -> None:
        self.vector_store = get_vector_store()
        self.logger = logging.getLogger(__name__)
        self.llm = ChatGroq(
            model=settings.SMALL_TEXT_MODEL_NAME,
            api_key=settings.GROQ_API_KEY,
            temperature=0.1,
            max_retries=2,
        ).with_structured_output(MemoryAnalysis)

    async def _analyze_memory(self, message: str) -> MemoryAnalysis:
        """Analyze a message to determine importance and format if needed."""
        prompt = MEMORY_ANALYSIS_PROMPT.format(message=message)
        
        self.logger.info(f"📝 Sending to LLM for analysis...")
        
        try:
            analysis = await self.llm.ainvoke(prompt)
            
            self.logger.info(f"🤖 LLM Response: {analysis}")
            
            if not isinstance(analysis, MemoryAnalysis):
                self.logger.warning("⚠️ LLM returned unexpected output, wrapping result")
                return MemoryAnalysis(is_important=False, formatted_memory=None)
            
            self.logger.info(f"✅ Analysis: is_important={analysis.is_important}, memory='{analysis.formatted_memory}'")
            
            return analysis
        except Exception as e:
            self.logger.exception(f"❌ Failed to analyze message: {e}")
            return MemoryAnalysis(is_important=False, formatted_memory=None)

    async def extract_and_store_memories(self, message: BaseMessage) -> None:
        """Extract important information from a message and store in vector store."""
        
        self.logger.info(f"🚪 extract_and_store_memories called")
        
        # Only store human messages
        if getattr(message, "type", None) != "human":
            self.logger.info(f"⏭️ Skipping non-human message (type: {getattr(message, 'type', 'unknown')})")
            return

        content = getattr(message, "content", "")
        if not content:
            self.logger.warning("⚠️ Empty message content; skipping")
            return

        self.logger.info(f"🧠 Analyzing message: '{content}'")

        # Analyze the message
        analysis = await self._analyze_memory(content)
        
        self.logger.info(f"📊 Analysis Result:")
        self.logger.info(f"   - is_important: {analysis.is_important}")
        self.logger.info(f"   - formatted_memory: '{analysis.formatted_memory}'")
        
        if analysis.is_important and analysis.formatted_memory:
            try:
                self.logger.info(f"🔍 Checking for similar memories...")
                similar = self.vector_store.find_similar_memory(analysis.formatted_memory)
                
                if similar:
                    self.logger.info(f"🔄 Similar memory found (score: {similar.score}): '{similar.text}'")
                else:
                    self.logger.info(f"✨ No similar memory found")
                    
            except Exception as e:
                self.logger.exception(f"❌ Error checking similarity: {e}")
                similar = None

            if similar:
                self.logger.info(f"⏭️ Skipping - similar memory exists")
                return

            # Store new memory
            try:
                memory_id = str(uuid.uuid4())
                self.logger.info(f"💾 STORING NEW MEMORY (ID: {memory_id})")
                self.logger.info(f"   Text: '{analysis.formatted_memory}'")
                
                self.vector_store.store_memory(
                    text=analysis.formatted_memory,
                    metadata={
                        "id": memory_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                
                self.logger.info(f"✅ MEMORY STORED SUCCESSFULLY! ID: {memory_id}")
                
            except Exception as e:
                self.logger.exception(f"❌ FAILED TO STORE MEMORY: {e}")
        else:
            self.logger.warning(f"❌ Message NOT important")
            self.logger.warning(f"   - is_important: {analysis.is_important}")

    def get_relevant_memories(self, context: str) -> List[str]:
        """Retrieve relevant memories based on the current context."""
        self.logger.info(f"🔍 Searching memories for: '{context[:100]}...'")
        
        try:
            memories = self.vector_store.search_memories(context, k=settings.MEMORY_TOP_K)
            self.logger.info(f"📚 Found {len(memories)} relevant memories")
        except Exception as e:
            self.logger.exception(f"❌ Error retrieving memories: {e}")
            return []

        if memories:
            for i, memory in enumerate(memories):
                try:
                    score = memory.score if getattr(memory, "score", None) is not None else 0.0
                    self.logger.info(f"   {i+1}. '{memory.text}' (score: {score:.4f})")
                except Exception:
                    self.logger.debug("Memory (malformed)")
        else:
            self.logger.info("   No memories found")
            
        return [getattr(memory, "text", "") for memory in memories]

    def format_memories_for_prompt(self, memories: List[str]) -> str:
        """Format retrieved memories as bullet points for inclusion in prompts."""
        if not memories:
            return ""
        formatted = "\n".join(f"- {m}" for m in memories)
        self.logger.info(f"📋 Formatted {len(memories)} memories for prompt")
        return formatted


def get_memory_manager() -> MemoryManager:
    """Get a MemoryManager instance."""
    return MemoryManager()