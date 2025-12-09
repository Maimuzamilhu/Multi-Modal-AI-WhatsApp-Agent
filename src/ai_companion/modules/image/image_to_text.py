import base64
import io
import logging
import os
from typing import Optional, Union

from PIL import Image

from ai_companion.core.exceptions import ImageToTextError
from ai_companion.settings import settings
from groq import Groq

class ImageToText:
    """A class to handle image-to-text conversion using Groq's vision capabilities."""

    REQUIRED_ENV_VARS = ["GROQ_API_KEY"]

    def __init__(self):
        """Initialize the ImageToText class and validate environment variables."""
        self._validate_env_vars()
        self._client: Optional[Groq] = None
        self.logger = logging.getLogger(__name__)

    def _validate_env_vars(self) -> None:
        """Validate that all required environment variables are set."""
        missing_vars = [var for var in self.REQUIRED_ENV_VARS if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    @property
    def client(self) -> Groq:
        """Get or create Groq client instance using singleton pattern."""
        if self._client is None:
            self._client = Groq(api_key=settings.GROQ_API_KEY)
        return self._client

    async def analyze_image(self, image_data: Union[str, bytes], prompt: str = "") -> str:
        """Analyze an image using Groq's vision capabilities.

        Args:
            image_data: Either a file path (str) or binary image data (bytes)
            prompt: Optional prompt to guide the image analysis

        Returns:
            str: Description or analysis of the image

        Raises:
            ValueError: If the image data is empty or invalid
            ImageToTextError: If the image analysis fails
        """
        try:
            self.logger.info("🖼️ Starting image analysis...")
            
            # Handle file path
            if isinstance(image_data, str):
                if not os.path.exists(image_data):
                    raise ValueError(f"Image file not found: {image_data}")
                with open(image_data, "rb") as f:
                    image_bytes = f.read()
            else:
                image_bytes = image_data

            if not image_bytes:
                raise ValueError("Image data cannot be empty")

            self.logger.info(f"📊 Original image size: {len(image_bytes)} bytes")

            # Process image with PIL to ensure compatibility
            try:
                img = Image.open(io.BytesIO(image_bytes))
                
                # Convert to RGB if needed (e.g. for PNGs with transparency or RGBA images)
                if img.mode in ('RGBA', 'P', 'LA'):
                    self.logger.info(f"🔄 Converting image from {img.mode} to RGB")
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize if too large (max 1024 on longest side for better performance)
                max_size = 1024
                if max(img.size) > max_size:
                    ratio = max_size / max(img.size)
                    new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    self.logger.info(f"📉 Resized image from {img.size} to {new_size}")

                # Convert to JPEG bytes
                output_buffer = io.BytesIO()
                img.save(output_buffer, format="JPEG", quality=90)
                image_bytes = output_buffer.getvalue()
                self.logger.info(f"✅ Processed image: {len(image_bytes)} bytes")
                
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to process image with PIL: {e}. Using original bytes.")
                # Continue with original bytes if PIL processing fails

            # Convert image to base64
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            # Improved default prompt with better instructions
            if not prompt:
                prompt = """Look at this image carefully and describe what you see in detail. Include:
- What the main subject is (person, object, scene, etc.)
- Physical characteristics (colors, clothing, expressions, etc.)
- The setting or background
- Any text or writing visible
- The mood or atmosphere
- Any other notable details

Provide a clear, descriptive response in a conversational tone."""

            self.logger.info(f"📝 Using prompt: '{prompt[:100]}...'")

            # Create the messages for the vision API
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ]

            # Make the API call with better parameters
            self.logger.info(f"🚀 Calling vision model: {settings.ITT_MODEL_NAME}")
            response = self.client.chat.completions.create(
                model=settings.ITT_MODEL_NAME,
                messages=messages,
                max_tokens=1500,
                temperature=0.3,
            )

            if not response.choices:
                raise ImageToTextError("No response received from the vision model")

            description = response.choices[0].message.content
            
            if not description or not description.strip():
                raise ImageToTextError("Empty response from vision model")
            
            description = description.strip()
            self.logger.info(f"✅ Generated image description ({len(description)} chars): '{description[:100]}...'")

            return description

        except Exception as e:
            self.logger.error(f"❌ Failed to analyze image: {e}", exc_info=True)
            raise ImageToTextError(f"Failed to analyze image: {str(e)}") from e