import logging
import os
import urllib.parse
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from ai_companion.core.exceptions import TextToImageError
from ai_companion.core.prompts import IMAGE_ENHANCEMENT_PROMPT, IMAGE_SCENARIO_PROMPT
from ai_companion.settings import settings
from langchain.prompts import PromptTemplate
from langchain_groq import ChatGroq


class ScenarioPrompt(BaseModel):
    """Class for the scenario response"""

    narrative: str = Field(..., description="The AI's narrative response to the question")
    image_prompt: str = Field(..., description="The visual prompt to generate an image representing the scene")


class EnhancedPrompt(BaseModel):
    """Class for the text prompt"""

    content: str = Field(
        ...,
        description="The enhanced text prompt to generate an image",
    )


class TextToImage:
    """A class to handle text-to-image generation using FREE Pollinations.ai API."""

    REQUIRED_ENV_VARS = ["GROQ_API_KEY"]

    def __init__(self):
        """Initialize the TextToImage class and validate environment variables."""
        self._validate_env_vars()
        self.logger = logging.getLogger(__name__)
        self.api_url = "https://image.pollinations.ai/prompt"

    def _validate_env_vars(self) -> None:
        """Validate that all required environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    async def generate_image(self, prompt: str, output_path: str = "") -> bytes:
        """Generate an image from a prompt using FREE Pollinations.ai API."""
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        try:
            self.logger.info(f"🎨 Generating image for prompt: '{prompt[:100]}...'")

            # Enhance the prompt first
            enhanced_prompt = await self.enhance_prompt(prompt)
            self.logger.info(f"✨ Enhanced prompt: '{enhanced_prompt[:100]}...'")

            # Use Pollinations.ai - FREE, no API key needed!
            encoded_prompt = urllib.parse.quote(enhanced_prompt)
            url = f"{self.api_url}/{encoded_prompt}"
            
            # Add parameters for better quality
            url += "?width=1024&height=768&model=flux&nologo=true"

            # Generate image
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                image_data = response.content
                self.logger.info(f"✅ Image generated successfully ({len(image_data)} bytes)")

            # Save if output path provided
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_data)
                self.logger.info(f"💾 Image saved to {output_path}")

            return image_data

        except httpx.HTTPError as e:
            self.logger.error(f"❌ HTTP error generating image: {e}")
            raise TextToImageError(f"Failed to generate image: HTTP error - {str(e)}") from e
        except Exception as e:
            self.logger.error(f"❌ Failed to generate image: {e}")
            raise TextToImageError(f"Failed to generate image: {str(e)}") from e

    async def create_scenario(self, chat_history: list = None) -> ScenarioPrompt:
        """Creates a first-person narrative scenario and corresponding image prompt based on chat history."""
        try:
            formatted_history = "\n".join([f"{msg.type.title()}: {msg.content}" for msg in chat_history[-5:]])

            self.logger.info("📝 Creating scenario from chat history")

            llm = ChatGroq(
                model=settings.TEXT_MODEL_NAME,
                api_key=settings.GROQ_API_KEY,
                temperature=0.7,
                max_retries=2,
            )

            structured_llm = llm.with_structured_output(ScenarioPrompt)

            chain = (
                PromptTemplate(
                    input_variables=["chat_history"],
                    template=IMAGE_SCENARIO_PROMPT,
                )
                | structured_llm
            )

            scenario = await chain.ainvoke({"chat_history": formatted_history})
            self.logger.info(f"✅ Created scenario: narrative='{scenario.narrative[:50]}...', prompt='{scenario.image_prompt[:50]}...'")

            return scenario

        except Exception as e:
            self.logger.error(f"❌ Failed to create scenario: {e}")
            # Return a fallback scenario instead of crashing
            return ScenarioPrompt(
                narrative="I'm imagining a beautiful scene...",
                image_prompt="beautiful landscape with mountains and sunset, digital art, high quality, detailed"
            )

    async def enhance_prompt(self, prompt: str) -> str:
        """Enhance a simple prompt with additional details and context."""
        try:
            self.logger.info(f"✨ Enhancing prompt: '{prompt[:50]}...'")

            llm = ChatGroq(
                model=settings.TEXT_MODEL_NAME,
                api_key=settings.GROQ_API_KEY,
                temperature=0.3,
                max_retries=2,
            )

            structured_llm = llm.with_structured_output(EnhancedPrompt)

            chain = (
                PromptTemplate(
                    input_variables=["prompt"],
                    template=IMAGE_ENHANCEMENT_PROMPT,
                )
                | structured_llm
            )

            enhanced = await chain.ainvoke({"prompt": prompt})
            enhanced_prompt = enhanced.content
            self.logger.info(f"✅ Enhanced prompt: '{enhanced_prompt[:100]}...'")

            return enhanced_prompt

        except Exception as e:
            self.logger.warning(f"⚠️ Failed to enhance prompt, using original with basic improvements: {e}")
            # Fallback to original prompt with basic enhancements
            return f"{prompt}, high quality, detailed, professional, 4k"