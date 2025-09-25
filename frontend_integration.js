// frontend_integration.js
// Update your React frontend to use the Python backend

// 1. Update your API configuration
const API_CONFIG = {
  // Use Python backend for local development
  BASE_URL: process.env.NODE_ENV === 'development' 
    ? 'http://localhost:8000'  // Python backend
    : 'your-firebase-function-url',  // Production Firebase Functions
    
  ENDPOINTS: {
    CHAT: '/chat',
    CONVERSATIONS: '/conversations',
    HEALTH: '/health'
  }
};

// 2. Updated chat service
class ChatService {
  static async sendMessage(conversationId, message, userId = "test-user", userEmail = "user@example.com") {
    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.CHAT}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversationId,
          message,
          userId,
          userEmail
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }

  static async handleTicketAction(conversationId, action, ticketData = null) {
    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.CHAT}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversationId,
          message: "",
          action,
          ticketData,
          userId: "test-user",
          userEmail: "user@example.com"
        })
      });

      return await response.json();
    } catch (error) {
      console.error('Error handling ticket action:', error);
      throw error;
    }
  }

  static async createConversation() {
    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.CONVERSATIONS}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      return await response.json();
    } catch (error) {
      console.error('Error creating conversation:', error);
      throw error;
    }
  }

  static async getConversationMessages(conversationId) {
    try {
      const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.ENDPOINTS.CONVERSATIONS}/${conversationId}/messages`);
      return await response.json();
    } catch (error) {
      console.error('Error getting messages:', error);
      throw error;
    }
  }
}

// 3. Example React component usage
const ExampleChatComponent = () => {
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [pendingApproval, setPendingApproval] = useState(null);

  // Initialize conversation
  useEffect(() => {
    const initConversation = async () => {
      try {
        const result = await ChatService.createConversation();
        setConversationId(result.conversationId);
      } catch (error) {
        console.error('Failed to create conversation:', error);
      }
    };
    
    initConversation();
  }, []);

  // Send message
  const handleSendMessage = async () => {
    if (!inputMessage.trim() || !conversationId) return;

    try {
      const result = await ChatService.sendMessage(conversationId, inputMessage);
      
      // Add messages to UI
      setMessages(prev => [
        ...prev,
        { role: 'user', content: inputMessage },
        { role: 'assistant', content: result.content }
      ]);

      // Check for approval needed
      if (result.needsApproval && result.interactiveButtons) {
        setPendingApproval({
          ticketData: result.interactiveButtons.buttons[0].data,
          summary: result.ticketSummary
        });
      }

      setInputMessage('');
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  // Handle ticket approval
  const handleTicketApproval = async (approved) => {
    if (!pendingApproval) return;

    try {
      const action = approved ? 'approve_ticket' : 'decline_ticket';
      const ticketData = approved ? pendingApproval.ticketData : null;
      
      const result = await ChatService.handleTicketAction(conversationId, action, ticketData);
      
      // Add response to messages
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: result.content }
      ]);

      setPendingApproval(null);
    } catch (error) {
      console.error('Error handling ticket action:', error);
    }
  };

  return (
    <div className="chat-interface">
      <div className="messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <strong>{msg.role === 'user' ? 'You' : 'Fixie'}:</strong> {msg.content}
          </div>
        ))}
      </div>

      {pendingApproval && (
        <div className="approval-buttons">
          <p>🔔 Ticket approval needed: {pendingApproval.summary}</p>
          <button onClick={() => handleTicketApproval(true)}>
            ✅ Create Ticket
          </button>
          <button onClick={() => handleTicketApproval(false)}>
            ❌ No Thanks
          </button>
        </div>
      )}

      <div className="input-area">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          placeholder="Type your IT support question..."
        />
        <button onClick={handleSendMessage}>Send</button>
      </div>
    </div>
  );
};

// 4. Test the integration
async function testIntegration() {
  console.log('🧪 Testing Frontend Integration');
  
  try {
    // Test health check
    const healthResponse = await fetch(`${API_CONFIG.BASE_URL}/health`);
    const healthData = await healthResponse.json();
    console.log('✅ Backend health:', healthData);

    // Test chat
    const chatResponse = await ChatService.sendMessage(
      'test-conversation',
      'My Zoom is not working, I tried everything'
    );
    console.log('✅ Chat response:', chatResponse);

    // Test ticket approval if needed
    if (chatResponse.needsApproval) {
      console.log('🔔 Testing ticket approval...');
      const approvalResponse = await ChatService.handleTicketAction(
        'test-conversation',
        'approve_ticket',
        chatResponse.interactiveButtons.buttons[0].data
      );
      console.log('✅ Ticket created:', approvalResponse);
    }

  } catch (error) {
    console.error('❌ Integration test failed:', error);
  }
}

// Export for use in your React app
export { ChatService, API_CONFIG, testIntegration };
