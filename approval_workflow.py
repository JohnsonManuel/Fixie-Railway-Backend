# approval_workflow.py
# Proper human-in-the-loop approval workflow for ticket creation

import json
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from config import Config
from agents import create_freshdesk_ticket

# State for approval workflow
class ApprovalState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage | ToolMessage], add_messages]
    user_id: str
    conversation_id: str
    user_email: str
    ticket_details: Optional[Dict[str, Any]]
    approval_needed: bool
    user_approved: bool

# Tool for generating ticket details (doesn't create ticket yet)
@tool
def generate_ticket_details(subject: str, description: str, priority: str, email: str) -> str:
    """
    Generate ticket details for user approval. This doesn't create the ticket yet.
    
    Args:
        subject: Clear, concise subject line describing the issue
        description: Detailed description of the problem including what was tried
        priority: Priority level (1=Low, 2=Medium, 3=High, 4=Urgent)
        email: User's email address for the ticket
    """
    print("📋 Generating ticket details for approval...")
    
    priority_names = {"1": "Low", "2": "Medium", "3": "High", "4": "Urgent"}
    priority_name = priority_names.get(priority, "Medium")
    
    ticket_preview = f"""I can help you create a support ticket for this issue. Here's what I'll include:

**Subject:** {subject}
**Description:** {description}
**Priority:** {priority_name}
**Email:** {email}

Would you like me to proceed with creating this ticket?"""
    
    print(f"📝 Generated ticket preview: {ticket_preview}")
    return ticket_preview

def create_approval_workflow():
    """Create the approval workflow for ticket creation"""
    
    llm = ChatOpenAI(
        api_key=Config.OPENAI_API_KEY,
        model=Config.CHAT_CONFIG["model"],
        temperature=Config.CHAT_CONFIG["temperature"]
    )
    
    # Bind the ticket details generation tool
    llm_with_tools = llm.bind_tools([generate_ticket_details])
    tool_node = ToolNode([generate_ticket_details])
    
    def analyze_for_ticket(state: ApprovalState):
        """Analyze conversation and generate ticket details for approval"""
        print("🔍 Approval Workflow: Analyzing for ticket creation...")
        
        system_prompt = f"""{Config.CHAT_CONFIG["systemPrompt"]}

You are now in TICKET CREATION MODE. The user has requested a support ticket.

Your task:
1. Analyze the conversation to understand the user's issue
2. Use the generate_ticket_details tool to create a ticket preview
3. Generate appropriate subject, description, and priority based on the conversation
4. Include the user's email address

TICKET DETAILS GUIDELINES:
- Subject: Clear, concise (e.g., "Zoom Application Not Working After Troubleshooting")
- Description: Include what issue they have, what they tried, and current status
- Priority: 1=Low, 2=Medium (default), 3=High, 4=Urgent
- Email: Use the email the user provided

The user will then approve or decline the ticket creation."""

        messages = [
            HumanMessage(content=system_prompt),
            *state["messages"]
        ]
        
        response = llm_with_tools.invoke(messages)
        print("📋 Approval Workflow: Generated ticket details for review")
        
        return {
            "messages": [response],
            "approval_needed": True
        }
    
    def should_generate_details(state: ApprovalState):
        """Check if we should generate ticket details"""
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            print("🔧 Approval Workflow: Generating ticket details")
            return "generate_details"
        return END
    
    def extract_ticket_data(state: ApprovalState):
        """Extract ticket data from tool calls for approval"""
        print("📊 Approval Workflow: Extracting ticket data...")
        
        messages = state["messages"]
        
        # Find the tool call with ticket details
        for message in reversed(messages):
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_call = message.tool_calls[0]
                if tool_call["name"] == "generate_ticket_details":
                    ticket_details = tool_call["args"]
                    print(f"📋 Extracted ticket details: {ticket_details}")
                    
                    return {
                        "ticket_details": ticket_details,
                        "approval_needed": True
                    }
        
        return {"approval_needed": False}
    
    # Build approval workflow graph
    workflow = StateGraph(ApprovalState)
    workflow.add_node("analyze", analyze_for_ticket)
    workflow.add_node("generate_details", tool_node)
    workflow.add_node("extract_data", extract_ticket_data)
    
    workflow.add_edge(START, "analyze")
    workflow.add_conditional_edges(
        "analyze",
        should_generate_details,
        {"generate_details": "generate_details", END: END}
    )
    workflow.add_edge("generate_details", "extract_data")
    workflow.add_edge("extract_data", END)
    
    return workflow.compile()

def run_approval_workflow(
    message: str,
    conversation_history: List[Dict[str, str]],
    user_id: str,
    conversation_id: str,
    user_email: str
) -> Dict[str, Any]:
    """
    Run the approval workflow for ticket creation
    """
    try:
        print('🔄 Starting Approval Workflow')
        
        workflow = create_approval_workflow()
        
        # Convert conversation history
        messages = []
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # Add current message
        messages.append(HumanMessage(content=message))
        
        # Run workflow
        result = workflow.invoke({
            "messages": messages,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "user_email": user_email,
            "ticket_details": None,
            "approval_needed": False,
            "user_approved": False
        })
        
        # Extract final response
        final_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        final_message = final_messages[-1] if final_messages else None
        
        if not final_message:
            raise Exception("No response generated")
        
        return {
            "content": final_message.content,
            "needsApproval": result.get("approval_needed", False),
            "ticketDetails": result.get("ticket_details"),
            "suggestions": None,
            "toolsUsed": ["generate_ticket_details"] if result.get("approval_needed") else [],
            "issueType": "ticket_approval"
        }
        
    except Exception as error:
        print(f'💥 Approval workflow error: {error}')
        raise error
