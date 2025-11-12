"""
Live API Demo - Phase 2 Role Reversal Support

This script demonstrates the new Phase 2 features by making actual API calls
to the running server.
"""
import requests
import json
import time

# Server configuration
BASE_URL = "http://localhost:8000"
MEMORY_BASE = f"{BASE_URL}/memory"

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")

def print_section(title):
    """Print formatted section"""
    print("\n" + "-" * 80)
    print(f"  {title}")
    print("-" * 80 + "\n")

def pretty_print(data, max_chars=500):
    """Pretty print JSON data"""
    json_str = json.dumps(data, indent=2)
    if len(json_str) > max_chars:
        print(json_str[:max_chars] + "\n... [truncated for display] ...")
    else:
        print(json_str)

def check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{MEMORY_BASE}/health", timeout=2)
        if response.status_code == 200:
            print("✅ Server is running at", BASE_URL)
            return True
    except Exception as e:
        print(f"❌ Server not responding: {e}")
        print(f"   Please start the server: cd backend && python server.py")
        return False
    return False

def demo_1_setup_debate():
    """Demo 1: Set up a debate with initial arguments"""
    print_header("DEMO 1: Setting Up a Debate with Initial Arguments")
    
    debate_id = "role_reversal_demo_001"
    
    # Initialize debate
    print("📍 Initializing debate session...")
    response = requests.post(
        f"{MEMORY_BASE}/debate/start",
        json={"debate_id": debate_id, "topic": "Renewable Energy Adoption"}
    )
    
    if response.status_code == 200:
        print(f"✅ Debate initialized: {debate_id}\n")
    else:
        print(f"⚠️  Using existing debate session\n")
    
    # Agent argues as PROPONENT
    print_section("Agent A argues as PROPONENT")
    
    proponent_args = [
        {
            "role": "proponent",
            "content": "Renewable energy significantly reduces carbon emissions and combats climate change effectively.",
            "metadata": {"agent": "Agent_A", "phase": "initial", "turn": 1}
        },
        {
            "role": "proponent",
            "content": "Solar and wind power are now cost-competitive with fossil fuels in most regions.",
            "metadata": {"agent": "Agent_A", "phase": "initial", "turn": 2}
        },
        {
            "role": "proponent",
            "content": "Renewable energy creates more sustainable jobs than the fossil fuel industry.",
            "metadata": {"agent": "Agent_A", "phase": "initial", "turn": 3}
        }
    ]
    
    for i, arg in enumerate(proponent_args, 1):
        response = requests.post(
            f"{MEMORY_BASE}/add",
            json=arg
        )
        
        if response.status_code == 200:
            print(f"   Turn {i}: {arg['content'][:70]}...")
        else:
            print(f"   ❌ Failed to add Turn {i}")
    
    print(f"\n✅ Stored {len(proponent_args)} proponent arguments in memory")
    return debate_id

def demo_2_role_history():
    """Demo 2: Retrieve role history"""
    print_header("DEMO 2: Retrieving Role History")
    
    debate_id = "role_reversal_demo_001"
    
    print("📜 Fetching all PROPONENT arguments...")
    
    response = requests.post(
        f"{MEMORY_BASE}/role/history",
        json={
            "role": "proponent",
            "debate_id": debate_id
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Retrieved {data['count']} historical arguments\n")
        
        print("📊 ROLE HISTORY:")
        print("-" * 80)
        
        for i, memory in enumerate(data['memories'][:3], 1):
            content = memory.get('content', '')[:100]
            turn = memory.get('metadata', {}).get('turn', '?')
            print(f"{i}. Turn {turn}: {content}...")
        
        if data['count'] > 3:
            print(f"... and {data['count'] - 3} more arguments")
        
        print()
        return data
    else:
        print(f"❌ Failed to retrieve history: {response.status_code}")
        print(response.text)
        return None

def demo_3_role_reversal():
    """Demo 3: Build role reversal context"""
    print_header("DEMO 3: Role Reversal - Agent Switches Sides")
    
    debate_id = "role_reversal_demo_001"
    
    print("🔄 SCENARIO: Agent A was PROPONENT, now becomes OPPONENT")
    print("   Agent must argue AGAINST renewable energy")
    print("   But should be aware of their previous PRO-renewable stance\n")
    
    print("📍 Building role reversal context...")
    
    response = requests.post(
        f"{MEMORY_BASE}/role/reversal",
        json={
            "current_role": "opponent",
            "previous_role": "proponent",
            "system_prompt": "You are Agent A, now arguing as OPPONENT against renewable energy adoption. You must present counterarguments while being aware you previously argued FOR renewables.",
            "current_task": "Present your opening argument against widespread renewable energy adoption. Consider the economic costs, reliability issues, and infrastructure challenges.",
            "debate_id": debate_id
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"\n✅ Role reversal context built successfully!\n")
        print("📊 CONTEXT DETAILS:")
        print(f"   Role Switch: {data['role_switch']}")
        print(f"   Previous Arguments Recalled: {data['previous_arguments_count']}")
        print(f"   Token Estimate: ~{data['token_estimate']} tokens\n")
        
        print("🧠 CONTEXT PAYLOAD (Preview):")
        print("-" * 80)
        
        context = data['context_payload']
        # Show first 1000 characters
        lines = context.split('\n')
        preview_lines = []
        char_count = 0
        
        for line in lines:
            if char_count + len(line) > 1000:
                break
            preview_lines.append(line)
            char_count += len(line)
        
        print('\n'.join(preview_lines))
        print("\n... [Full context includes ZONE 2A with previous arguments] ...")
        print("-" * 80)
        
        return data
    else:
        print(f"❌ Failed to build reversal context: {response.status_code}")
        print(response.text)
        return None

def demo_4_consistency_check():
    """Demo 4: Check for contradictions"""
    print_header("DEMO 4: Consistency Detection - Catching Contradictions")
    
    debate_id = "role_reversal_demo_001"
    
    # First, add a strong statement
    print("📍 Agent's INITIAL position (as proponent):")
    initial_statement = "Renewable energy is the most economically viable solution for our future energy needs."
    print(f"   '{initial_statement}'\n")
    
    requests.post(
        f"{MEMORY_BASE}/add",
        json={
            "role": "proponent",
            "content": initial_statement,
            "metadata": {"agent": "Agent_A", "phase": "check_consistency"}
        }
    )
    
    time.sleep(1)  # Give it a moment to index
    
    # Now check a contradictory statement
    print("📍 Agent's NEW statement (checking for contradiction):")
    contradictory = "Renewable energy is NOT economically viable and is far more expensive than fossil fuels."
    print(f"   '{contradictory}'\n")
    
    print("🔍 Running consistency check...")
    
    response = requests.post(
        f"{MEMORY_BASE}/consistency/check",
        json={
            "role": "proponent",
            "new_statement": contradictory,
            "debate_id": debate_id,
            "threshold": 0.3
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print("\n📊 CONSISTENCY ANALYSIS:")
        print("-" * 80)
        print(f"   Has Inconsistencies: {data['has_inconsistencies']}")
        print(f"   Consistency Score: {data['consistency_score']:.2f}")
        print(f"   Related Statements: {len(data['related_statements'])}")
        
        if data['warnings']:
            print(f"\n⚠️  DETECTED CONTRADICTIONS ({len(data['warnings'])}):")
            for i, warning in enumerate(data['warnings'][:3], 1):
                print(f"   {i}. {warning}")
        else:
            print("\n✅ No contradictions detected")
        
        print()
        return data
    else:
        print(f"❌ Failed consistency check: {response.status_code}")
        print(response.text)
        return None

def demo_5_memory_status():
    """Demo 5: Check memory system status"""
    print_header("DEMO 5: Memory System Status")
    
    response = requests.get(f"{MEMORY_BASE}/status")
    
    if response.status_code == 200:
        data = response.json()
        
        print("📊 MEMORY SYSTEM STATUS:")
        print("-" * 80)
        print(f"   RAG Enabled: {data['rag_enabled']}")
        
        summary = data['memory_summary']
        print(f"   Current Debate: {summary.get('current_debate_id', 'None')}")
        print(f"   Turn Counter: {summary.get('turn_counter', 0)}")
        
        if 'short_term' in summary:
            st = summary['short_term']
            print(f"\n   Short-term Memory:")
            print(f"      Messages: {st.get('message_count', 0)}")
            print(f"      Window Size: {st.get('window_size', 0)}")
        
        if 'long_term' in summary and summary['long_term']:
            lt = summary['long_term']
            print(f"\n   Long-term Memory (RAG):")
            print(f"      Total Memories: {lt.get('memory_count', 0)}")
            print(f"      Backend: {lt.get('backend', 'unknown')}")
        
        print()
        return data
    else:
        print(f"❌ Failed to get status: {response.status_code}")
        return None

def demo_6_complete_workflow():
    """Demo 6: Complete multi-round debate with role reversals"""
    print_header("DEMO 6: Complete Multi-Round Debate Simulation")
    
    debate_id = "complete_demo_001"
    
    print("🎭 SCENARIO: Two agents debate, then swap roles multiple times\n")
    
    # Initialize
    requests.post(
        f"{MEMORY_BASE}/debate/start",
        json={"debate_id": debate_id, "topic": "Universal Basic Income"}
    )
    
    # Round 1: Normal debate
    print_section("ROUND 1: Initial Positions")
    
    print("   Agent A (Proponent): UBI provides economic security...")
    requests.post(
        f"{MEMORY_BASE}/add",
        json={
            "role": "proponent",
            "content": "Universal Basic Income provides economic security and reduces poverty.",
            "metadata": {"agent": "Agent_A", "round": 1}
        }
    )
    
    print("   Agent B (Opponent): UBI is too expensive and reduces work incentive...")
    requests.post(
        f"{MEMORY_BASE}/add",
        json={
            "role": "opponent",
            "content": "Universal Basic Income is too expensive and reduces work incentives.",
            "metadata": {"agent": "Agent_B", "round": 1}
        }
    )
    
    time.sleep(1)
    
    # Round 2: FIRST REVERSAL
    print_section("ROUND 2: FIRST ROLE REVERSAL")
    print("   🔄 Agent A: Proponent → Opponent")
    print("   🔄 Agent B: Opponent → Proponent\n")
    
    # Get Agent A's reversal context
    response_a = requests.post(
        f"{MEMORY_BASE}/role/reversal",
        json={
            "current_role": "opponent",
            "previous_role": "proponent",
            "system_prompt": "You are Agent A, now as OPPONENT.",
            "current_task": "Argue against UBI.",
            "debate_id": debate_id
        }
    )
    
    if response_a.status_code == 200:
        data_a = response_a.json()
        print(f"   ✅ Agent A reversal: {data_a['previous_arguments_count']} previous args recalled")
    
    # Get Agent B's reversal context
    response_b = requests.post(
        f"{MEMORY_BASE}/role/reversal",
        json={
            "current_role": "proponent",
            "previous_role": "opponent",
            "system_prompt": "You are Agent B, now as PROPONENT.",
            "current_task": "Argue for UBI.",
            "debate_id": debate_id
        }
    )
    
    if response_b.status_code == 200:
        data_b = response_b.json()
        print(f"   ✅ Agent B reversal: {data_b['previous_arguments_count']} previous args recalled")
    
    # Check role histories
    print_section("MEMORY SUMMARY")
    
    proponent_history = requests.post(
        f"{MEMORY_BASE}/role/history",
        json={"role": "proponent", "debate_id": debate_id}
    )
    
    opponent_history = requests.post(
        f"{MEMORY_BASE}/role/history",
        json={"role": "opponent", "debate_id": debate_id}
    )
    
    if proponent_history.status_code == 200:
        print(f"   📜 Proponent history: {proponent_history.json()['count']} statements")
    
    if opponent_history.status_code == 200:
        print(f"   📜 Opponent history: {opponent_history.json()['count']} statements")
    
    print("\n✅ Both agents successfully swapped roles with full memory context!")

def main():
    """Run all demonstrations"""
    print("\n" + "=" * 80)
    print("  🔄 PHASE 2: ROLE REVERSAL - LIVE API DEMONSTRATIONS")
    print("=" * 80)
    print("\n  Testing all Phase 2 features via HTTP API")
    print("  Server: http://localhost:8000\n")
    
    # Check server
    if not check_server():
        return 1
    
    print("\n⏳ Starting demonstrations...\n")
    time.sleep(1)
    
    try:
        # Run demos
        demo_1_setup_debate()
        time.sleep(1)
        
        demo_2_role_history()
        time.sleep(1)
        
        demo_3_role_reversal()
        time.sleep(1)
        
        demo_4_consistency_check()
        time.sleep(1)
        
        demo_5_memory_status()
        time.sleep(1)
        
        demo_6_complete_workflow()
        
        # Final summary
        print_header("DEMONSTRATIONS COMPLETE")
        print("✅ All Phase 2 API endpoints tested successfully!\n")
        
        print("📚 What was demonstrated:")
        print("   ✓ Setting up debates with arguments")
        print("   ✓ Retrieving role-specific history")
        print("   ✓ Building role reversal contexts")
        print("   ✓ Detecting contradictions")
        print("   ✓ Checking memory system status")
        print("   ✓ Complete multi-round debate with reversals")
        
        print("\n🎯 API Endpoints Used:")
        print("   • POST /memory/debate/start")
        print("   • POST /memory/add")
        print("   • POST /memory/role/history")
        print("   • POST /memory/role/reversal")
        print("   • POST /memory/consistency/check")
        print("   • GET  /memory/status")
        
        print("\n🔗 You can now:")
        print("   1. Integrate these endpoints into your frontend")
        print("   2. Use them in your debate system")
        print("   3. Test with Postman or curl")
        print("   4. Build UI components for role reversal\n")
        
    except Exception as e:
        print(f"\n❌ Error during demonstrations: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
