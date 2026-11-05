from langchain_core.messages import HumanMessage
from db.checkpointer import get_checkpointer
from orchestrator.graph import graph

def run_conversations():
    print("=== Testing 5 Sample Conversations ===")
    
    conversations = [
        # 1. Simple FAQ
        {"user": "user1", "queries": ["What is your return policy?"]},
        
        # 2. Multi-turn FAQ
        {"user": "user2", "queries": ["I forgot my password.", "How long does the reset link last?"]},
        
        # 3. Action intent
        {"user": "user3", "queries": ["I want to check my order status."]},
        
        # 4. Complex intent
        {"user": "user4", "queries": ["I am extremely angry, nothing is working and I want to speak to a manager!"]},
        
        # 5. Out of scope / low confidence
        {"user": "user5", "queries": ["What is the capital of France?"]},
    ]
    
    with get_checkpointer() as memory:
        compiled_graph = graph.compile(checkpointer=memory)
        for i, conv in enumerate(conversations):
            print(f"\n--- Conversation {i+1} ({conv['user']}) ---")
            thread = {"configurable": {"thread_id": conv["user"]}}
            
            for q in conv["queries"]:
                print(f"User: {q}")
                
                # For simplicity, we just pass the new message, 
                # the checkpointer maintains the full state history.
                initial_state = {"messages": [HumanMessage(content=q)]}
                
                # Run graph
                final_state = compiled_graph.invoke(initial_state, thread)
                
                # The final AI message
                final_messages = final_state["messages"]
                if final_messages:
                    last_msg = final_messages[-1]
                    print(f"Agent: {last_msg.content}")
                    print(f"[State info: Intent={final_state.get('intent')}, Confidence={final_state.get('confidence', 0)}]")
                
if __name__ == "__main__":
    run_conversations()
