  #docker-compose -f docker-compose.ngrok.yml up -d
# docker-compose -f docker-compose.ngrok.yml down 
# http://localhost:4040
#docker logs whatsapp -f
# docker logs chainlit -f


# Stop everything
docker-compose -f docker-compose.ngrok.yml down

# Remove old containers
docker rm -f chainlit whatsapp ngrok

# Rebuild both
docker-compose -f docker-compose.ngrok.yml build

# Start everything
docker-compose -f docker-compose.ngrok.yml up -d

# Watch logs in separate terminals
# Terminal 1:
docker logs chainlit -f

# Terminal 2:
docker logs whatsapp -f
```

### 6. Test Both Interfaces

**Test Chainlit:**
1. Open http://localhost:8000
2. Send: `My name is Muzamil and I study AI`
3. Check logs for memory storage

**Test WhatsApp:**
1. Send message to your WhatsApp test number
2. Send: `I love playing cricket`
3. Check WhatsApp logs

### 7. Verify in Qdrant

Go to your Qdrant dashboard and you should see multiple points now!

### Expected Logs:

**Chainlit:**
```
🆔 New Chainlit session started with thread_id: abc123...
📨 [Chainlit] Processing message for thread abc123: 'My name is Muzamil...'
🚀 [Chainlit] Invoking graph for thread abc123
🔥 MEMORY_EXTRACTION_NODE CALLED!
🚪 extract_and_store_memories called
🧠 Analyzing message: 'My name is Muzamil and I study AI'
📊 Analysis Result:
   - is_important: True
   - formatted_memory: 'User's name is Muzamil. User studies AI.'
💾 STORING NEW MEMORY (ID: xyz789)
✅ MEMORY STORED SUCCESSFULLY!
```

**WhatsApp:**
```
📱 Message from: +92XXX, session_id: +92XXX
💬 Text message: I love playing cricket
🚀 Invoking graph for session +92XXX...
🔥 MEMORY_EXTRACTION_NODE CALLED!
🚪 extract_and_store_memories called
💾 STORING NEW MEMORY (ID: abc456)
✅ MEMORY STORED SUCCESSFULLY!