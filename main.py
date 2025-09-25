# main.py
# Python FastAPI backend replicating Firebase Functions logic

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime
import json

from config import Config
from agents import run_multi_agent_workflow, create_ticket_directly
from approval_workflow import run_approval_workflow

app = FastAPI(title="Fixie AI Chat Backend", version="1.0.0")

# CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Config.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for local testing (replace with database in production)
conversations_db = {}
messages_db = {}

# Request/Response models
class ChatMessage(BaseModel):
    role: str
    content: str
    createdAt: Optional[str] = None

class ChatRequest(BaseModel):
    conversationId: str
    message: str
    userId: Optional[str] = "test-user"
    userEmail: Optional[str] = "user@example.com"
    action: Optional[str] = None
    ticketData: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    success: bool
    messageId: str
    content: str
    conversationId: str
    needsApproval: Optional[bool] = False
    ticketSummary: Optional[str] = None
    interactiveButtons: Optional[Dict[str, Any]] = None
    ticketCreated: Optional[bool] = False
    ticketId: Optional[str] = None
    ticketNumber: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Fixie AI Chat Backend - Python Version", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint - replicates Firebase Functions chat logic
    """
    try:
        print(f'Chat request received: {request.message[:50]}...')
        
        # Validate required fields
        # if not request.conversationId or not request.message:
        #     raise HTTPException(status_code=400, detail="Missing conversationId or message")
        
        user_id = request.userId or "test-user"
        user_email = request.userEmail or "user@example.com"
        
        # Handle ticket creation approval
        if request.action == 'approve_ticket' and request.ticketData:
            print('🎫 User approved ticket creation')
            print(f'📋 Ticket data: {json.dumps(request.ticketData, indent=2)}')
            print(f'👤 User email: {user_email}')
            
            ticket_result = create_ticket_directly(request.ticketData, user_email)
            print(f'🎯 Ticket creation result: {ticket_result}')
            
            # Save ticket creation response to "database"
            message_id = str(uuid.uuid4())
            message_data = {
                "role": "assistant",
                "content": ticket_result["content"],
                "createdAt": datetime.now().isoformat(),
                "ticketId": ticket_result.get("ticketId"),
                "ticketNumber": ticket_result.get("ticketNumber")
            }
            
            # Store in memory
            if request.conversationId not in messages_db:
                messages_db[request.conversationId] = []
            messages_db[request.conversationId].append(message_data)
            
            return ChatResponse(
                success=True,
                messageId=message_id,
                content=ticket_result["content"],
                conversationId=request.conversationId,
                ticketCreated=ticket_result["success"],
                ticketId=ticket_result.get("ticketId"),
                ticketNumber=ticket_result.get("ticketNumber")
            )
        
        # Handle ticket decline
        if request.action == 'decline_ticket':
            print('User declined ticket creation')
            
            decline_message = "I understand you don't want to create a ticket right now. Is there anything else I can help you with?"
            
            message_id = str(uuid.uuid4())
            message_data = {
                "role": "assistant",
                "content": decline_message,
                "createdAt": datetime.now().isoformat()
            }
            
            # Store in memory
            if request.conversationId not in messages_db:
                messages_db[request.conversationId] = []
            messages_db[request.conversationId].append(message_data)
            
            return ChatResponse(
                success=True,
                messageId=message_id,
                content=decline_message,
                conversationId=request.conversationId
            )
        
        # Normal chat flow
        # Get conversation history from memory
        conversation_messages = messages_db.get(request.conversationId, [])
        
        # Build conversation context
        chat_msgs = []
        for msg in conversation_messages:
            chat_msgs.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        chat_msgs.append({
            "role": "user", 
            "content": request.message
        })
        
        # Check if this is a ticket creation request
        message_lower = request.message.lower()
        ticket_keywords = ["create ticket", "create a ticket", "yes", "proceed", "confirm"]
        
        if any(keyword in message_lower for keyword in ticket_keywords):
            print('🎫 Using Approval Workflow for ticket creation')
            workflow_result = run_approval_workflow(
                request.message, 
                chat_msgs[:-1],
                user_id, 
                request.conversationId,
                user_email
            )
        else:
            print('🚀 Using Multi-Agent LangGraph workflow')
            workflow_result = run_multi_agent_workflow(
                request.message, 
                chat_msgs[:-1],  # Don't include the current message in history
                user_id, 
                request.conversationId,
                user_email
            )
        
        ai_response = workflow_result["content"]
        
        # Save user message
        user_message_id = str(uuid.uuid4())
        user_message_data = {
            "role": "user",
            "content": request.message,
            "createdAt": datetime.now().isoformat()
        }
        
        # Save AI response
        ai_message_id = str(uuid.uuid4())
        ai_message_data = {
            "role": "assistant",
            "content": ai_response,
            "createdAt": datetime.now().isoformat()
        }
        
        # Store in memory
        if request.conversationId not in messages_db:
            messages_db[request.conversationId] = []
        
        messages_db[request.conversationId].extend([user_message_data, ai_message_data])
        
        # Update conversation metadata
        conversations_db[request.conversationId] = {
            "lastMessage": request.message,
            "updatedAt": datetime.now().isoformat(),
            "userId": user_id
        }
        
        # Prepare response
        response = ChatResponse(
            success=True,
            messageId=ai_message_id,
            content=ai_response,
            conversationId=request.conversationId
        )
        
        # Add approval buttons for ticket creation
        if workflow_result.get("needsApproval") and workflow_result.get("ticketDetails"):
            response.needsApproval = True
            response.ticketSummary = workflow_result["ticketDetails"]["subject"]
            response.interactiveButtons = {
                "type": "ticket_approval",
                "buttons": [
                    {
                        "id": "approve_ticket",
                        "label": "✅ Create Ticket",
                        "action": "approve_ticket",
                        "data": workflow_result["ticketDetails"]
                    },
                    {
                        "id": "decline_ticket",
                        "label": "❌ No Thanks",
                        "action": "decline_ticket"
                    }
                ]
            }
        
        return response
        
    except Exception as error:
        print(f'💥 Chat error: {type(error).__name__}: {error}')
        import traceback
        print(f'📍 Full traceback: {traceback.format_exc()}')
        
        # Handle different types of errors
        if "auth" in str(error).lower():
            raise HTTPException(
                status_code=401,
                detail="Authentication failed. Please refresh and try again."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Sorry, I encountered an error: {str(error)}"
            )

@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: str):
    """Get conversation history"""
    messages = messages_db.get(conversation_id, [])
    return {"messages": messages}

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation metadata"""
    conversation = conversations_db.get(conversation_id, {})
    return {"conversation": conversation}

@app.post("/conversations")
async def create_conversation():
    """Create a new conversation"""
    conversation_id = str(uuid.uuid4())
    conversations_db[conversation_id] = {
        "createdAt": datetime.now().isoformat(),
        "updatedAt": datetime.now().isoformat(),
        "title": "New Chat"
    }
    return {"conversationId": conversation_id}

@app.get("/debug/conversations")
async def debug_conversations():
    """Debug endpoint to see all conversations"""
    return {
        "conversations": conversations_db,
        "total_conversations": len(conversations_db),
        "total_messages": sum(len(msgs) for msgs in messages_db.values())
    }

@app.post("/test/ticket")
async def test_ticket_creation():
    """Direct ticket creation test endpoint"""
    try:
        print("🧪 Direct ticket creation test endpoint called")
        
        test_ticket_data = {
            "subject": "Direct API Test Ticket",
            "description": "This is a direct test of the ticket creation API endpoint",
            "priority": "2",
            "email": "kingmaker@gmail.com"
        }
        
        result = create_ticket_directly(test_ticket_data, "kingmaker@gmail.com")
        
        return {
            "success": result["success"],
            "message": "Direct ticket test completed",
            "ticketResult": result
        }
        
    except Exception as error:
        print(f'💥 Direct ticket test error: {error}')
        raise HTTPException(
            status_code=500,
            detail=f"Direct ticket test failed: {str(error)}"
        )

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Fixie AI Chat Backend...")
    print(f"🌐 Frontend URL: {Config.FRONTEND_URL}")
    print(f"🔑 OpenAI API Key: {'✅ Set' if Config.OPENAI_API_KEY != 'your-openai-api-key-here' else '❌ Not set'}")
    print(f"🎫 Freshdesk Domain: {Config.FRESHDESK_DOMAIN}")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
