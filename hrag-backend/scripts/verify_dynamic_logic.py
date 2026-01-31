
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from app.domain_init import initialize_domain_system
from app.domain_config import DomainRegistry
from app.state import GraphState, DynamicSlotInfo
from app.nodes.input_guard import _get_classification_prompt
from app.nodes.retrieval import graph_search_node
# Use mock for retrieval to avoid DB connection errors
from unittest.mock import MagicMock, patch

async def verify_dynamic_system():
    print("Starting Dynamic System Verification...")
    
    # 1. Initialize Domain System
    print("\n[1] Initializing Domain System...")
    try:
        initialize_domain_system()
        domains = DomainRegistry.list_domains()
        print(f"Discovered domains: {domains}")
        
        if "email" not in domains:
            print("Failed to discover 'email' domain")
            return
            
        DomainRegistry.set_active("email")
        active = DomainRegistry.get_active()
        print(f"Active domain set to: {active.display_name}")
        
    except Exception as e:
        print(f"Initialization failed: {e}")
        return

    # 2. Verify Prompt Generation (Input Guard)
    print("\n[2] Verifying Input Guard Prompts...")
    try:
        prompt_template = _get_classification_prompt(active)
        messages = prompt_template.format_messages(query="Find emails from Jeff")
        system_msg = messages[0].content
        
        if "IntentClassifier" in system_msg and "Email Assistant" in system_msg:
             print("Classification prompt correctly loaded from email.yaml")
             print(f"   Identity: {system_msg.splitlines()[0]}")
        else:
             print("Prompt content mismatch")
             print(system_msg)
             
    except Exception as e:
        print(f"Prompt verification failed: {e}")

    # 3. Verify Graph Query Selection (Simulation)
    print("\n[3] Verifying Graph Retrieval Logic...")
    state = {
        "query": "Find emails about California", 
        "slots": DynamicSlotInfo(slots={"topic": "California"})
    }
    
    # Mock the Neo4j driver and session
    from app.nodes.retrieval import Neo4jClient
    
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()
    
    mock_driver.session.return_value.__aenter__.return_value = mock_session
    mock_session.run.return_value = mock_result
    mock_result.data.return_value = asyncio.Future()
    mock_result.data.return_value.set_result([]) # Return empty list
    
    # Patch the driver getter
    with patch.object(Neo4jClient, 'get_driver', return_value=mock_driver):
        # We also need to patch asyncio.create_task or run purely graph_search_node
        # Let's run graph_search_node directly
        await graph_search_node(state)
        
        # Check what query was passed to session.run
        calls = mock_session.run.call_args_list
        if calls:
            args, kwargs = calls[0]
            query_str = args[0]
            params = kwargs
            
            print("Graph search executed")
            if "MATCH (e:Email)" in query_str:
                print("Correct 'primary_search' query from email.yaml used")
            else:
                print(f"Unexpected query used: {query_str[:50]}...")
            
            if params.get("topic") == "California":
                 print("Parameters correctly bound (topic='California')")
            else:
                 print(f"Parameter binding failed: {params}")
        else:
            print("No Neo4j query executed")

    print("\nVerification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_dynamic_system())
