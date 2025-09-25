# agents.py
# LangGraph agents for chat and ticket management

import json
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.graph.message import add_messages
from datetime import datetime
import requests
import base64
from config import Config

# Shared state for all agents
class AgentState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage | ToolMessage], add_messages]
    user_id: str
    conversation_id: str
    user_email: str
    current_agent: str
    ticket_data: Optional[Dict[str, Any]]
    needs_approval: bool

# Tool for ticket creation
@tool
def create_freshdesk_ticket(subject: str, description: str, priority: str, email: str) -> str:
    """
    Create a support ticket in Freshdesk when user needs escalation to human support.
    
    Args:
        subject: Clear, concise subject line describing the issue
        description: Detailed description of the problem including what was tried
        priority: Priority level (1=Low, 2=Medium, 3=High, 4=Urgent) 
        email: User's email address for the ticket
    """
    try:
        print("🎫 Ticket Agent: Starting ticket creation...")
        print(f"📋 Ticket params: {json.dumps({'subject': subject, 'description': description, 'priority': priority, 'email': email}, indent=2)}")
        
        domain = Config.FRESHDESK_DOMAIN
        api_key = Config.FRESHDESK_API_KEY
        
        print(f"🌐 Domain: {domain}")
        print(f"🔑 API Key: {api_key[:10]}..." if api_key else "❌ No API key")
        
        if not domain or not api_key or api_key == "your-freshdesk-api-key-here":
            print("❌ Configuration issue - missing domain or API key")
            return "❌ Unable to create tickets due to configuration issues. Please contact support directly."

        # Use exact format from your working curl command
        ticket_data = {
            "description": description,
            "subject": subject,
            "email": email,
            "priority": int(priority),
            "status": 2
        }
        
        print(f"📝 Ticket data: {json.dumps(ticket_data, indent=2)}")

        # Create base64 encoded auth header (matching curl format)
        auth_string = f"{api_key}:X"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        print(f"🔐 Auth header: Basic {auth_b64[:20]}...")

        api_url = f"https://{domain}/api/v2/tickets"
        print(f"🌐 API URL: {api_url}")

        print("📡 Ticket Agent: Making API request to Freshdesk...")
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

        if not response.ok:
            error_text = response.text
            print(f'❌ Freshdesk API error: {response.status_code}')
            print(f'❌ Error response: {error_text}')
            
            try:
                error_json = response.json()
                print(f'❌ Parsed error: {json.dumps(error_json, indent=2)}')
                
                if error_json.get('code') == 'invalid_credentials':
                    return "❌ Authentication failed with Freshdesk. Please check API credentials."
                elif 'email' in error_text.lower():
                    return "❌ Email validation failed. Please provide a valid email address."
                else:
                    return f"❌ Freshdesk API error: {error_json.get('message', 'Unknown error')}"
            except:
                return f"❌ Freshdesk API error {response.status_code}: {error_text}"

        ticket = response.json()
        print(f"✅ Ticket Agent: Ticket created successfully!")
        print(f"🎫 Ticket details: {json.dumps(ticket, indent=2)}")
        
        ticket_url = f"https://{domain}/a/tickets/{ticket['id']}"
        priority_names = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
        priority_name = priority_names.get(int(priority), "Medium")
        
        return f"""✅ **Support ticket created successfully!**

**Ticket ID:** #{ticket['id']}
**Subject:** {subject}
**Priority:** {priority_name}

**View your ticket:** {ticket_url}

Our IT support team will review your request and respond within 24 hours. You'll receive email updates as we work on your issue."""

    except Exception as error:
        print(f'💥 Ticket Agent error: {type(error).__name__}: {error}')
        import traceback
        print(f'📍 Full traceback: {traceback.format_exc()}')
        return "❌ Unexpected error while creating ticket. Please contact support directly."

# Chat Agent - handles general IT support conversations
def create_chat_agent():
    """Create the chat agent for general IT support"""
    
    llm = ChatOpenAI(
        api_key=Config.OPENAI_API_KEY,
        model=Config.CHAT_CONFIG["model"],
        temperature=Config.CHAT_CONFIG["temperature"]
    )
    
    def chat_node(state: AgentState):
        """Chat agent node - provides IT support and decides when to escalate"""
        print("💬 Chat Agent: Processing message...")
        
        # Enhanced system prompt for chat agent
        system_prompt = f"""{Config.CHAT_CONFIG["systemPrompt"]}

ESCALATION GUIDELINES:
- If user explicitly requests ticket creation, ask for their email address first
- If user has tried multiple solutions and still needs help, suggest ticket creation
- If user expresses frustration or urgency, suggest ticket creation
- Always ask for user confirmation AND email before creating tickets

TICKET CREATION PROCESS:
1. When user wants a ticket, ask: "I can create a support ticket for you. Please provide your email address."
2. Once you have their email, ask: "Would you like me to proceed with creating the ticket?"
3. DO NOT create tickets automatically - always get explicit approval
4. If user provides email and confirms, then suggest they use the ticket creation tool

IMPORTANT: Never create tickets without explicit user approval and email address.
"""

        messages = [
            HumanMessage(content=system_prompt),
            *state["messages"]
        ]
        
        response = llm.invoke(messages)
        print(f"💬 Chat Agent: Generated response (length: {len(response.content)})")
        
        return {
            "messages": [response],
            "current_agent": "chat"
        }
    
    # Build chat agent graph
    workflow = StateGraph(AgentState)
    workflow.add_node("chat", chat_node)
    workflow.add_edge(START, "chat")
    workflow.add_edge("chat", END)
    
    return workflow.compile()

# Ticket Agent - handles ticket creation with approval workflow
def create_ticket_agent():
    """Create the ticket agent for handling support ticket creation"""
    
    llm = ChatOpenAI(
        api_key=Config.OPENAI_API_KEY,
        model=Config.CHAT_CONFIG["model"],
        temperature=Config.CHAT_CONFIG["temperature"]
    )
    
    # Bind the ticket creation tool to the LLM
    llm_with_tools = llm.bind_tools([create_freshdesk_ticket])
    tool_node = ToolNode([create_freshdesk_ticket])
    
    def ticket_analysis_node(state: AgentState):
        """Analyze the conversation and prepare ticket details"""
        print("🎫 Ticket Agent: Analyzing conversation for ticket creation...")
        
        system_prompt = """You are a specialized Ticket Creation Agent. Your job is to:

1. Analyze the conversation history to understand the user's issue
2. Generate appropriate ticket details (subject, description, priority)
3. Use the create_freshdesk_ticket tool to create the ticket

TICKET CREATION GUIDELINES:
- Create clear, concise subject lines
- Include detailed descriptions with what was tried
- Set appropriate priority based on urgency and impact
- Use the user's email address

PRIORITY LEVELS:
- 1 (Low): General questions, minor issues
- 2 (Medium): Standard IT issues affecting one user
- 3 (High): Issues affecting multiple users or business functions
- 4 (Urgent): Critical system outages, security issues

Generate the ticket details and use the create_freshdesk_ticket tool."""

        messages = [
            HumanMessage(content=system_prompt),
            *state["messages"]
        ]
        
        response = llm_with_tools.invoke(messages)
        print(f"🎫 Ticket Agent: Generated response with tools")
        
        return {
            "messages": [response],
            "current_agent": "ticket"
        }
    
    def should_use_tools(state: AgentState):
        """Decide whether to use tools or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            print("🔧 Ticket Agent: Using tools to create ticket")
            return "tools"
        return END
    
    # Build ticket agent graph
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", ticket_analysis_node)
    workflow.add_node("tools", tool_node)
    
    workflow.add_edge(START, "analyze")
    workflow.add_conditional_edges(
        "analyze",
        should_use_tools,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", END)
    
    return workflow.compile()

# Supervisor Agent - routes between chat and ticket agents
def create_supervisor_agent():
    """Create supervisor agent that routes between chat and ticket agents"""
    
    llm = ChatOpenAI(
        api_key=Config.OPENAI_API_KEY,
        model=Config.CHAT_CONFIG["model"],
        temperature=0.3  # Lower temperature for routing decisions
    )
    
    def supervisor_node(state: AgentState):
        """Supervisor decides which agent should handle the request"""
        print("🎯 Supervisor Agent: Routing request...")
        
        last_message = state["messages"][-1] if state["messages"] else None
        user_input = last_message.content if last_message else ""
        
        routing_prompt = f"""You are a Supervisor Agent that routes user requests to the appropriate specialist agent.

AVAILABLE AGENTS:
- CHAT: Handles general IT support, troubleshooting, and conversations
- TICKET: Handles support ticket creation when escalation is needed

ROUTING RULES:
- Route to CHAT for: general IT questions, troubleshooting, normal conversation
- Route to TICKET for: explicit ticket creation requests, escalation after failed troubleshooting

USER REQUEST: {user_input}

Based on the request, which agent should handle this? Respond with only: CHAT or TICKET"""

        response = llm.invoke([HumanMessage(content=routing_prompt)])
        agent_choice = response.content.strip().upper()
        
        print(f"🎯 Supervisor: Routing to {agent_choice} agent")
        
        return {
            "current_agent": agent_choice.lower(),
            "messages": state["messages"]
        }
    
    def route_to_agent(state: AgentState):
        """Route to the appropriate agent"""
        return state["current_agent"]
    
    # Build supervisor graph
    workflow = StateGraph(AgentState)
    workflow.add_node("supervisor", supervisor_node)
    
    workflow.add_edge(START, "supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {"chat": "chat", "ticket": "ticket"}
    )
    
    return workflow.compile()

# Main multi-agent workflow
def create_multi_agent_workflow():
    """Create the main multi-agent workflow"""
    
    chat_agent = create_chat_agent()
    ticket_agent = create_ticket_agent()
    
    def chat_agent_node(state: AgentState):
        """Run the chat agent"""
        print("💬 Running Chat Agent...")
        result = chat_agent.invoke(state)
        return result
    
    def ticket_agent_node(state: AgentState):
        """Run the ticket agent"""
        print("🎫 Running Ticket Agent...")
        result = ticket_agent.invoke(state)
        return result
    
    def supervisor_routing(state: AgentState):
        """Supervisor routing logic"""
        last_message = state["messages"][-1] if state["messages"] else None
        user_input = last_message.content.lower() if last_message else ""
        
        # Simple routing logic
        ticket_keywords = [
            "create ticket", "create a ticket", "open ticket", "submit ticket",
            "escalate", "human help", "support team", "manager"
        ]
        
        if any(keyword in user_input for keyword in ticket_keywords):
            print("🎯 Supervisor: Routing to TICKET agent")
            return "ticket"
        else:
            print("🎯 Supervisor: Routing to CHAT agent") 
            return "chat"
    
    # Build main workflow
    workflow = StateGraph(AgentState)
    
    # Add agent nodes
    workflow.add_node("chat_agent", chat_agent_node)
    workflow.add_node("ticket_agent", ticket_agent_node)
    
    # Supervisor routing
    workflow.add_conditional_edges(
        START,
        supervisor_routing,
        {"chat": "chat_agent", "ticket": "ticket_agent"}
    )
    
    workflow.add_edge("chat_agent", END)
    workflow.add_edge("ticket_agent", END)
    
    return workflow.compile()

# Main function to run the multi-agent workflow
def run_multi_agent_workflow(
    message: str,
    conversation_history: List[Dict[str, str]],
    user_id: str,
    conversation_id: str,
    user_email: str = "customer@example.com"
) -> Dict[str, Any]:
    """
    Run the multi-agent LangGraph workflow
    """
    try:
        print('🚀 Starting Multi-Agent LangGraph Workflow')
        
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == "your-openai-api-key-here":
            raise Exception("OpenAI API key not available")

        # Create the workflow
        workflow = create_multi_agent_workflow()
        
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
            "user_email": user_email,
            "current_agent": "",
            "ticket_data": None,
            "needs_approval": False
        })
        
        # Extract the final response
        final_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
        final_message = final_messages[-1] if final_messages else None
        
        if not final_message:
            raise Exception("No response generated from agents")
        
        # Check if ticket creation was attempted
        tool_messages = [msg for msg in result["messages"] if isinstance(msg, ToolMessage)]
        ticket_created = any("✅" in msg.content for msg in tool_messages)
        ticket_id = None
        
        if ticket_created:
            # Extract ticket ID from tool message
            for msg in tool_messages:
                if "Ticket ID:" in msg.content:
                    import re
                    ticket_id_match = re.search(r'Ticket ID:\*\* #(\w+)', msg.content)
                    ticket_id = ticket_id_match.group(1) if ticket_id_match else None
                    break
        
        print(f'✅ Multi-Agent Workflow completed - Agent: {result.get("current_agent", "unknown")}')
        
        return {
            "content": final_message.content,
            "needsApproval": False,  # Agents handle their own approval
            "suggestions": None,
            "toolsUsed": ["create_freshdesk_ticket"] if ticket_created else [],
            "issueType": result.get("current_agent", "general"),
            "ticketCreated": ticket_created,
            "ticketId": ticket_id
        }

    except Exception as error:
        print(f'💥 Multi-Agent Workflow error: {error}')
        import traceback
        print(f'📍 Full traceback: {traceback.format_exc()}')
        raise error

# Direct ticket creation for approval workflow
def create_ticket_directly(ticket_data: Dict[str, Any], user_email: str) -> Dict[str, Any]:
    """
    Create ticket directly using the tool (for approval workflow)
    """
    try:
        print('🎫 Direct Ticket Creation: User approved')
        print(f'🎫 Direct Ticket Creation: Ticket data: {ticket_data}')
        # Create input dict for the tool
        tool_input = {
            "subject": ticket_data["subject"],
            "description": ticket_data["description"], 
            "priority": ticket_data["priority"],
            "email": user_email
        }
        result = create_freshdesk_ticket.invoke(tool_input)
        
        # Extract ticket ID
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
        print(f'💥 Direct ticket creation error: {error}')
        return {
            "success": False,
            "content": "❌ Error creating ticket. Please contact support directly."
        }
