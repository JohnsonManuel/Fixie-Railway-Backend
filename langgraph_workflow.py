# langgraph_workflow.py
# Proper LangGraph workflow with tool calling for ticket creation

import json
import requests
import base64
from datetime import datetime
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from config import Config

# Define the conversation state for LangGraph
class ConversationState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage | ToolMessage], add_messages]
    user_id: str
    conversation_id: str
    needs_approval: bool
    pending_ticket: Optional[Dict[str, Any]]

# Define the ticket creation tool using LangChain
@tool
def create_support_ticket(subject: str, description: str, priority: str, email: str) -> str:
    """
    Create a support ticket when user explicitly requests it or when troubleshooting hasn't resolved their issue.
    Only use when user clearly needs escalation to human support.
    
    Args:
        subject: Clear, concise subject line describing the issue
        description: Detailed description of the problem including what was tried and current status
        priority: Priority level (1=Low, 2=Medium, 3=High, 4=Urgent)
        email: User's email address for the ticket
    """
    try:
        print("🎫 Starting ticket creation process...")
        print(f"📋 Ticket params: {json.dumps({'subject': subject, 'description': description, 'priority': priority, 'email': email}, indent=2)}")
        
        domain = Config.FRESHDESK_DOMAIN
        api_key = Config.FRESHDESK_API_KEY
        
        print(f"🌐 Domain: {domain}")
        print(f"🔑 API Key: {api_key[:10]}..." if api_key else "❌ No API key")
        
        if not domain or not api_key or api_key == "your-freshdesk-api-key-here":
            print("❌ Configuration issue - missing domain or API key")
            return "I apologize, but I'm unable to create tickets at the moment due to configuration issues. Please contact support directly."
        
        # Use real Freshdesk API call (matching your working curl command)

        ticket_data = {
            "description": description,
            "subject": subject,
            "email": email,
            "priority": int(priority),
            "status": 2
        }
        
        print(f"📝 Ticket data: {json.dumps(ticket_data, indent=2)}")

        # Create base64 encoded auth header
        auth_string = f"{api_key}:X"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        print(f"🔐 Auth header created: Basic {auth_b64[:20]}...")

        api_url = f"https://{domain}/api/v2/tickets"
        print(f"🌐 API URL: {api_url}")

        print("📡 Making API request to Freshdesk...")
        response = requests.post(
            api_url,
            headers={
                'Authorization': f'Basic {auth_b64}',
                'Content-Type': 'application/json'
            },
            json=ticket_data,
            timeout=30
        )

        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response headers: {dict(response.headers)}")

        if not response.ok:
            error_text = response.text
            print(f'❌ Freshdesk API error: {response.status_code}')
            print(f'❌ Error response: {error_text}')
            
            # Parse error for better user message
            try:
                error_json = response.json()
                print(f'❌ Parsed error: {json.dumps(error_json, indent=2)}')
                
                if error_json.get('code') == 'invalid_credentials':
                    return "❌ Authentication failed with Freshdesk. Please check the API credentials."
                elif 'email' in error_text.lower():
                    return "❌ Email validation failed. Please provide a valid email address."
                else:
                    return f"❌ Freshdesk API error: {error_json.get('message', 'Unknown error')}"
            except:
                return f"❌ Freshdesk API error {response.status_code}: {error_text}"

        ticket = response.json()
        print(f"✅ Ticket created successfully: {json.dumps(ticket, indent=2)}")
        
        ticket_url = f"https://{domain}/a/tickets/{ticket['id']}"
        
        priority_names = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
        priority_name = priority_names.get(int(priority), "Medium")
        
        print(f"🔗 Ticket URL: {ticket_url}")
        
        return f"""✅ **Support ticket created successfully!**

**Ticket ID:** #{ticket['id']}
**Subject:** {subject}
**Priority:** {priority_name}

**View your ticket:** {ticket_url}

Our IT support team will review your request and respond within 24 hours. You'll receive email updates as we work on your issue."""

    except requests.exceptions.Timeout:
        print("⏰ Freshdesk API timeout")
        return "❌ Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        print("🌐 Connection error to Freshdesk")
        return "❌ Cannot connect to Freshdesk. Please check your internet connection."
    except Exception as error:
        print(f'💥 Unexpected error creating ticket: {type(error).__name__}: {error}')
        import traceback
        print(f'📍 Full traceback: {traceback.format_exc()}')
        return "❌ I encountered an unexpected error while creating your ticket. Please contact our support team directly."

# Create the LangGraph workflow
def create_langgraph_workflow():
    """Create the actual LangGraph workflow"""
    
    # Initialize the LLM with tools
    llm = ChatOpenAI(
        api_key=Config.OPENAI_API_KEY,
        model=Config.CHAT_CONFIG["model"],
        temperature=Config.CHAT_CONFIG["temperature"]
    )
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools([create_support_ticket])
    
    # Create tool node
    tool_node = ToolNode([create_support_ticket])
    
    # Define workflow nodes
    def chatbot(state: ConversationState):
        """Main chatbot node - processes messages and decides on tool usage"""
        # Enhanced system prompt with tool instructions
        enhanced_system_prompt = f"""{Config.CHAT_CONFIG["systemPrompt"]}

AVAILABLE TOOLS:
- create_support_ticket: Use this tool when the user explicitly asks to create a ticket, or when you've provided troubleshooting steps but the user indicates they still need help and want to escalate to human support.

TOOL USAGE GUIDELINES:
- ONLY use create_support_ticket when:
  1. User explicitly asks to "create a ticket" or "escalate to support"
  2. User has tried your suggestions and still needs help
  3. User expresses frustration and wants human assistance
  4. The issue is complex and requires human intervention

- Generate appropriate ticket details based on the conversation context
- Use user's email from the conversation or ask for it if needed

IMPORTANT: Be helpful with troubleshooting first. Only suggest ticket creation when appropriate."""

        # Add system message if not already present
        messages = state["messages"]
        if not messages or not any(isinstance(msg, AIMessage) and "Fixie" in str(msg.content) for msg in messages):
            system_message = HumanMessage(content=enhanced_system_prompt)
            messages = [system_message] + messages
        
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    
    def should_continue(state: ConversationState):
        """Decide whether to continue to tools or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If the last message has tool calls, continue to tools
        if last_message.tool_calls:
            return "tools"
        # Otherwise end
        return END
    
    # Build the graph
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("chatbot", chatbot)
    workflow.add_node("tools", tool_node)
    
    # Add edges
    workflow.add_edge(START, "chatbot")
    workflow.add_conditional_edges(
        "chatbot",
        should_continue,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "chatbot")
    
    return workflow.compile()

def run_chat_workflow(
    message: str,
    conversation_history: List[Dict[str, str]],
    user_id: str,
    conversation_id: str
) -> Dict[str, Any]:
    """
    Run the LangGraph workflow
    """
    try:
        print('Starting LangGraph workflow')
        
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == "your-openai-api-key-here":
            raise Exception("OpenAI API key not available")

        # Create the workflow
        workflow = create_langgraph_workflow()
        
        # Convert conversation history to LangChain messages
        messages = []
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # Add current user message
        messages.append(HumanMessage(content=message))
        
        # Run the workflow
        result = workflow.invoke({
            "messages": messages,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "needs_approval": False,
            "pending_ticket": None
        })
        
        # Extract the final AI message
        final_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        final_message = final_messages[-1] if final_messages else None
        
        if not final_message:
            raise Exception("No AI response generated")
        
        # Check if there were tool calls that need approval
        tool_calls_made = any(msg.tool_calls for msg in result["messages"] if hasattr(msg, 'tool_calls') and msg.tool_calls)
        
        if tool_calls_made:
            # Find the tool call details
            for msg in result["messages"]:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    tool_call = msg.tool_calls[0]
                    if tool_call["name"] == "create_support_ticket":
                        # Extract tool arguments for approval
                        tool_args = tool_call["args"]
                        priority_names = {"1": "Low", "2": "Medium", "3": "High", "4": "Urgent"}
                        priority_name = priority_names.get(tool_args["priority"], "Medium")
                        
                        return {
                            "content": f"""I can help you create a support ticket for this issue. Here's what I'll include:

**Subject:** {tool_args['subject']}
**Description:** {tool_args['description']}
**Priority:** {priority_name}

Would you like me to proceed with creating this ticket?""",
                            "needsApproval": True,
                            "suggestions": None,
                            "toolsUsed": ["create_support_ticket"],
                            "issueType": "ticket_creation",
                            "pendingTicket": tool_args
                        }
        
        print('LangGraph workflow completed - no tools used')
        
        return {
            "content": final_message.content,
            "needsApproval": False,
            "suggestions": None,
            "toolsUsed": [],
            "issueType": "general"
        }

    except Exception as error:
        print(f'Error in LangGraph workflow: {error}')
        raise error

def create_ticket_with_approval(ticket_data: Dict[str, Any], user_email: str) -> Dict[str, Any]:
    """
    Execute ticket creation after user approval using the LangChain tool
    """
    try:
        print('Creating ticket with user approval')
        
        # Call the ticket creation function directly
        result = create_support_ticket(
            subject=ticket_data["subject"],
            description=ticket_data["description"], 
            priority=ticket_data["priority"],
            email=user_email
        )
        
        # Extract ticket ID from result if successful
        import re
        ticket_id_match = re.search(r'Ticket ID:\*\* #(\w+)', result)
        ticket_id = ticket_id_match.group(1) if ticket_id_match else None
        
        return {
            "success": "✅" in result,
            "content": result,
            "ticketId": ticket_id,
            "ticketNumber": ticket_id
        }
        
    except Exception as error:
        print(f'Error in ticket creation with approval: {error}')
        return {
            "success": False,
            "content": "I apologize, but I encountered an error while creating your ticket. Please contact our support team directly."
        }