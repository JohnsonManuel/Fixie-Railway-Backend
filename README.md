# 🐍 Python Backend for Fixie AI Chat

This Python backend replicates your Firebase Functions logic with LangGraph workflow for local testing.

## 🚀 Quick Start

### 1. Setup Environment
```bash
cd python-backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux  
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file:
```env
OPENAI_API_KEY=your-actual-openai-api-key-here
FRESHDESK_DOMAIN=yourcompany.freshdesk.com
FRESHDESK_API_KEY=your-freshdesk-api-key-here
FRONTEND_URL=http://localhost:3000
```

### 3. Start the Server
```bash
python main.py
```

Server will start at: `http://localhost:8000`

### 4. Update Frontend
Change your frontend API URL from Firebase Functions to:
```javascript
// In your React app
const API_URL = "http://localhost:8000";

// Update your chat API call
const response = await fetch(`${API_URL}/chat`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    conversationId: conversationId,
    message: message,
    userId: "test-user",
    userEmail: "user@example.com"
  })
});
```

## 🔧 API Endpoints

### POST `/chat`
Main chat endpoint - identical to your Firebase Function

**Request:**
```json
{
  "conversationId": "conv-123",
  "message": "My Zoom is not working",
  "userId": "user-123",
  "userEmail": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "messageId": "msg-456",
  "content": "I can help with your Zoom issue...",
  "conversationId": "conv-123",
  "needsApproval": false
}
```

**With Ticket Approval:**
```json
{
  "success": true,
  "content": "I can create a ticket for you...",
  "needsApproval": true,
  "ticketSummary": "Zoom Not Working",
  "interactiveButtons": {
    "type": "ticket_approval",
    "buttons": [
      {
        "id": "approve_ticket",
        "label": "✅ Create Ticket",
        "action": "approve_ticket",
        "data": { "subject": "...", "description": "..." }
      },
      {
        "id": "decline_ticket", 
        "label": "❌ No Thanks",
        "action": "decline_ticket"
      }
    ]
  }
}
```

### POST `/chat` (Approval Actions)
Handle ticket approval/decline

**Approve Request:**
```json
{
  "conversationId": "conv-123",
  "message": "",
  "action": "approve_ticket",
  "ticketData": {
    "subject": "Zoom Not Working",
    "description": "User experiencing issues...",
    "priority": "2",
    "email": "user@example.com"
  }
}
```

**Decline Request:**
```json
{
  "conversationId": "conv-123", 
  "message": "",
  "action": "decline_ticket"
}
```

### GET `/conversations/{id}/messages`
Get conversation history

### GET `/debug/conversations`
Debug endpoint to see all stored conversations

## 🧪 Testing Features

### 1. **LangGraph Tool Calling**
- AI automatically decides when to use ticket creation tool
- No hardcoded logic - pure AI decision making
- Test with: "I tried everything and it's still broken"

### 2. **Human-in-the-Loop Approval**
- AI asks for confirmation before creating tickets
- Interactive buttons for approve/decline
- Test the approval workflow

### 3. **Freshdesk Integration**
- Real API calls to Freshdesk (if configured)
- Professional ticket creation responses
- Proper error handling

### 4. **Conversation Persistence**
- Messages stored in memory (like Firebase)
- Conversation history maintained
- Full conversation context

## 🎯 Test Scenarios

### **Basic Chat:**
```
POST /chat
{
  "conversationId": "test-1",
  "message": "Hello, I need help"
}
```

### **Trigger Tool Usage:**
```
POST /chat
{
  "conversationId": "test-2", 
  "message": "My Zoom is broken, I tried restarting it but it's still not working. I need human help."
}
```

### **Direct Ticket Request:**
```
POST /chat
{
  "conversationId": "test-3",
  "message": "Please create a support ticket for me"
}
```

## 🔄 Frontend Integration

Update your React frontend to use the Python backend:

```javascript
// utils/api.js
const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:8000'  // Python backend
  : 'your-firebase-function-url';  // Production

export const sendChatMessage = async (conversationId, message) => {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      conversationId,
      message,
      userId: "test-user",
      userEmail: "user@example.com"
    })
  });
  
  return response.json();
};

export const handleTicketAction = async (conversationId, action, ticketData = null) => {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      conversationId,
      message: "",
      action,
      ticketData
    })
  });
  
  return response.json();
};
```

## 🎮 How to Test

1. **Start Python backend**: `python main.py`
2. **Update frontend** to use `http://localhost:8000`
3. **Test scenarios**:
   - Normal chat
   - Request ticket creation
   - Test approval buttons
4. **Check debug endpoint**: `GET http://localhost:8000/debug/conversations`

## 🔧 Development Benefits

- **🧪 Local Testing**: No Firebase deployment needed
- **⚡ Fast Iteration**: Instant code changes
- **🔍 Easy Debugging**: Python debugging tools
- **💰 Cost Free**: No Firebase Functions costs
- **🎯 Isolated Testing**: Test just the AI logic

Your Python backend now perfectly replicates your Firebase Functions with full LangGraph workflow support! 🎉
