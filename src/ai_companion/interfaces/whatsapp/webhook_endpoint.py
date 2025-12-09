from fastapi import FastAPI
from ai_companion.interfaces.whatsapp.whatsapp_response import whatsapp_router

# Create FastAPI app instance
app = FastAPI(
    title="Ava WhatsApp Agent",
    description="WhatsApp interface for Ava AI companion",
    version="1.0.0"
)

# Include the WhatsApp router
app.include_router(whatsapp_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "whatsapp"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Ava WhatsApp Agent is running",
        "endpoints": ["/health", "/whatsapp_response", "/docs"]
    }