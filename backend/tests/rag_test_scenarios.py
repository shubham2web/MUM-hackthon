"""
RAG Test Scenarios - Comprehensive Test Cases

This module defines all test scenarios for validating RAG retrieval quality.
Includes debate scenarios, chat scenarios, OCR scenarios, and ATLAS-specific
role reversal tests.
"""

from typing import List, Tuple, Dict, Any


def create_debate_test_cases(benchmark) -> None:
    """
    Test cases for debate memory retrieval.
    
    These tests validate that the RAG system can correctly retrieve:
    - Specific turn content
    - Arguments by topic
    - Arguments by role
    - Recent context
    """
    
    # Test 1: Exact turn recall
    benchmark.add_test_case(
        scenario_name="Exact Turn Recall",
        setup_memories=[
            ("moderator", "Welcome to the debate on nuclear energy safety.", {"turn": 0}),
            ("proponent", "Nuclear energy is the safest energy source with lowest death rate per TWh according to WHO statistics.", {"turn": 1}),
            ("opponent", "Nuclear waste remains dangerous for thousands of years requiring costly long-term storage.", {"turn": 2}),
            ("proponent", "Modern Generation IV reactors have passive safety systems that prevent meltdowns.", {"turn": 3}),
        ],
        query="What did the proponent say about safety in turn 1?",
        expected_memories=[1],  # Index of turn 1
        relevance_threshold=0.90,
        description="Tests ability to retrieve exact turn content when explicitly requested"
    )
    
    # Test 2: Semantic topic search
    benchmark.add_test_case(
        scenario_name="Topic-Based Retrieval",
        setup_memories=[
            ("proponent", "Nuclear provides 24/7 baseload power unlike intermittent solar energy.", {"turn": 1, "topic": "reliability"}),
            ("opponent", "Solar panel costs have dropped 90% in the last decade making it highly affordable.", {"turn": 2, "topic": "economics"}),
            ("proponent", "France gets 70% of electricity from nuclear with some of the lowest costs in Europe.", {"turn": 3, "topic": "economics"}),
            ("opponent", "Battery storage technology now solves the solar intermittency problem effectively.", {"turn": 4, "topic": "reliability"}),
        ],
        query="Arguments about economic costs and affordability",
        expected_memories=[1, 2],  # Indices of economics-related turns
        relevance_threshold=0.85,
        description="Tests semantic search for topic-related arguments across multiple turns"
    )
    
    # Test 3: Role-specific filtering
    benchmark.add_test_case(
        scenario_name="Role Filtering",
        setup_memories=[
            ("proponent", "Nuclear has the smallest carbon footprint of any energy source at 12g CO2/kWh.", {"turn": 1}),
            ("opponent", "Renewable energy is truly carbon-free with zero emissions during operation.", {"turn": 2}),
            ("proponent", "Uranium mining has minimal environmental impact compared to rare earth mining for batteries.", {"turn": 3}),
            ("opponent", "Wind and solar require no fuel extraction, reducing environmental damage significantly.", {"turn": 4}),
        ],
        query="What environmental arguments did the opponent make?",
        expected_memories=[1, 3],  # Opponent's turns (indices 1 and 3)
        relevance_threshold=0.85,
        description="Tests ability to filter memories by role metadata"
    )
    
    # Test 4: Temporal recency
    benchmark.add_test_case(
        scenario_name="Recent Context Retrieval",
        setup_memories=[
            ("proponent", "Initial argument about safety from turn 1.", {"turn": 1}),
            ("opponent", "Initial counter about waste from turn 2.", {"turn": 2}),
            ("proponent", "Early rebuttal about containment from turn 3.", {"turn": 3}),
            ("opponent", "Recent argument referencing Chernobyl and Fukushima disasters.", {"turn": 8}),
            ("proponent", "Latest response about modern Generation IV reactor designs and inherent safety.", {"turn": 9}),
        ],
        query="Most recent arguments in the debate about modern technology",
        expected_memories=[3, 4],  # Last 2 turns (indices 3, 4)
        relevance_threshold=0.80,
        description="Tests ability to prioritize recent context over older content"
    )
    
    # Test 5: Negative case (no false positives)
    benchmark.add_test_case(
        scenario_name="Irrelevant Query Handling",
        setup_memories=[
            ("proponent", "Nuclear energy provides clean baseload power for the grid.", {"turn": 1}),
            ("opponent", "Nuclear plants are expensive and take too long to build.", {"turn": 2}),
        ],
        query="What was said about cryptocurrency mining and blockchain technology?",
        expected_memories=[],  # Should retrieve nothing - topic not discussed
        relevance_threshold=0.85,
        description="Tests that system doesn't hallucinate or return false positives for irrelevant queries"
    )


def create_role_reversal_test_cases(benchmark) -> None:
    """
    Test cases specifically for ATLAS's Role Reversal feature.
    
    This is a CRITICAL test - role reversal requires the RAG system to:
    1. Overcome the current agent's prompt (ZONE 1)
    2. Retrieve factual historical context about the OPPOSITE position
    3. Enable the agent to argue against their original stance
    """
    
    # Test 6: Role Reversal - Retrieve Original Stance
    benchmark.add_test_case(
        scenario_name="Role Reversal - Original Stance Retrieval",
        setup_memories=[
            ("proponent", "Solar energy is cheap, efficient, and will power our sustainable future.", {"turn": 1, "phase": "original"}),
            ("opponent", "Solar is unreliable, intermittent, and requires massive battery storage infrastructure.", {"turn": 2, "phase": "original"}),
            ("proponent", "Solar panel efficiency has improved dramatically, now reaching 22% conversion rates.", {"turn": 3, "phase": "original"}),
            ("opponent", "Cloudy weather and nighttime mean solar cannot provide baseload power reliably.", {"turn": 4, "phase": "original"}),
            # Now roles reverse - proponent must argue AGAINST solar
        ],
        query="What was my original argument FOR solar energy that I now need to critique?",
        expected_memories=[0, 2],  # Original proponent arguments (indices 0, 2)
        relevance_threshold=0.85,
        description="CRITICAL: Tests if reversed agent can retrieve their original position to argue against it"
    )
    
    # Test 7: Role Reversal - Retrieve Opponent's Arguments
    benchmark.add_test_case(
        scenario_name="Role Reversal - Adopt Opponent's Position",
        setup_memories=[
            ("proponent", "Nuclear energy is essential for climate goals with its low carbon footprint.", {"turn": 1}),
            ("opponent", "Nuclear waste creates environmental hazards lasting millennia.", {"turn": 2}),
            ("opponent", "Nuclear accidents like Chernobyl show catastrophic risks.", {"turn": 3}),
            ("proponent", "Modern reactors have passive safety preventing accidents.", {"turn": 4}),
            # Proponent reverses - must now use opponent's arguments
        ],
        query="What arguments against nuclear energy should I now adopt after role reversal?",
        expected_memories=[1, 2],  # Opponent's arguments (indices 1, 2)
        relevance_threshold=0.85,
        description="Tests if reversed agent can adopt the opponent's previous arguments as their own"
    )


def create_chat_test_cases(benchmark) -> None:
    """
    Test cases for multi-turn chat retrieval.
    
    These tests validate conversational context retrieval for:
    - Follow-up questions
    - Topic switching
    - Historical reference
    """
    
    # Test 8: Follow-up context
    benchmark.add_test_case(
        scenario_name="Multi-Turn Chat Context",
        setup_memories=[
            ("user", "What is quantum entanglement?", {"type": "question"}),
            ("assistant", "Quantum entanglement is when particles remain connected such that measuring one instantly affects the other, regardless of distance.", {"type": "answer"}),
            ("user", "Can you give an example?", {"type": "question"}),
            ("assistant", "Imagine two entangled photons. If you measure one as horizontally polarized, the other will be vertical, even if they're light-years apart.", {"type": "answer"}),
        ],
        query="What did you explain about entanglement earlier?",
        expected_memories=[1],  # First assistant response (index 1)
        relevance_threshold=0.85,
        description="Tests retrieval of previous explanations in multi-turn conversation"
    )
    
    # Test 9: Multi-topic conversation
    benchmark.add_test_case(
        scenario_name="Topic Switching",
        setup_memories=[
            ("user", "Tell me about AI safety risks.", {"topic": "ai_safety"}),
            ("assistant", "AI safety focuses on alignment problems, ensuring AI systems act according to human values and intentions.", {"topic": "ai_safety"}),
            ("user", "What about climate change impacts?", {"topic": "climate"}),
            ("assistant", "Climate change is causing rising temperatures, extreme weather, and sea level rise due to greenhouse gas emissions.", {"topic": "climate"}),
            ("user", "Back to AI - what are the biggest alignment challenges?", {"topic": "ai_safety"}),
        ],
        query="Previous discussion about AI safety concerns and alignment",
        expected_memories=[1],  # First AI safety response (index 1)
        relevance_threshold=0.85,
        description="Tests ability to retrieve correct topic context after switching topics"
    )


def create_ocr_test_cases(benchmark) -> None:
    """
    Test cases for OCR image analysis retrieval.
    
    These tests validate that the system can:
    - Reference previously analyzed images
    - Connect related OCR analyses
    - Retrieve fact-checking context
    """
    
    # Test 10: OCR historical reference
    benchmark.add_test_case(
        scenario_name="OCR Context Recall",
        setup_memories=[
            ("user", "OCR from image: 'COVID-19 vaccine contains microchips for tracking'", {"type": "ocr", "image": 1}),
            ("assistant", "This is misinformation. No vaccines contain microchips. This false claim has been thoroughly debunked by medical experts.", {"type": "fact_check"}),
            ("user", "OCR from image: 'Vaccine side effects chart showing 95% adverse reactions'", {"type": "ocr", "image": 2}),
            ("assistant", "This chart appears to be misleading. Clinical trials showed normal immune responses (soreness, fatigue) in a minority of recipients, not 95% adverse reactions.", {"type": "fact_check"}),
        ],
        query="What did we find about vaccine misinformation earlier?",
        expected_memories=[1],  # First fact-check (index 1)
        relevance_threshold=0.85,
        description="Tests retrieval of previous OCR fact-checking analyses"
    )
    
    # Test 11: Cross-reference multiple OCR analyses
    benchmark.add_test_case(
        scenario_name="Multi-Image Context",
        setup_memories=[
            ("user", "OCR: 'Climate hoax - temperatures haven't changed in 50 years'", {"type": "ocr"}),
            ("assistant", "This is false. Global temperature data from NASA shows 1.1°C increase since 1880.", {"type": "fact_check"}),
            ("user", "OCR: 'Polar ice caps growing, not shrinking'", {"type": "ocr"}),
            ("assistant", "Incorrect. Arctic sea ice has declined 13% per decade since 1979 according to NSIDC.", {"type": "fact_check"}),
            ("user", "Are these claims related?", {"type": "question"}),
        ],
        query="Previous climate misinformation we analyzed",
        expected_memories=[1, 3],  # Both fact-checks (indices 1, 3)
        relevance_threshold=0.80,
        description="Tests ability to connect related misinformation across multiple images"
    )


def create_edge_case_test_cases(benchmark) -> None:
    """
    Edge cases and stress tests for RAG retrieval.
    """
    
    # Test 12: Very similar content disambiguation
    benchmark.add_test_case(
        scenario_name="Similar Content Disambiguation",
        setup_memories=[
            ("proponent", "Nuclear power plants emit zero carbon during operation.", {"turn": 1}),
            ("proponent", "Nuclear power plants emit minimal carbon during their full lifecycle.", {"turn": 2}),
            ("proponent", "Nuclear power plants have the lowest carbon footprint of any energy source.", {"turn": 3}),
        ],
        query="What was said about carbon emissions during plant operation specifically?",
        expected_memories=[0],  # First statement about operation (index 0)
        relevance_threshold=0.85,
        description="Tests ability to distinguish between very similar statements"
    )
    
    # Test 13: Long-term memory retention
    benchmark.add_test_case(
        scenario_name="Long-Term Memory Retention",
        setup_memories=[
            ("proponent", "Opening statement: Solar is the future of energy.", {"turn": 1}),
            ("opponent", "Counter: Solar is too expensive.", {"turn": 2}),
            ("proponent", "Rebuttal about costs.", {"turn": 3}),
            ("opponent", "Rebuttal about reliability.", {"turn": 4}),
            ("proponent", "Convergence statement.", {"turn": 5}),
            ("opponent", "Convergence statement.", {"turn": 6}),
            ("proponent", "Synthesis.", {"turn": 7}),
            ("opponent", "Synthesis.", {"turn": 8}),
            ("moderator", "Final summary.", {"turn": 9}),
        ],
        query="What was the opening statement about solar energy?",
        expected_memories=[0],  # First turn (index 0)
        relevance_threshold=0.85,
        description="Tests retrieval of early content after many subsequent memories"
    )


def load_all_test_scenarios(benchmark) -> None:
    """
    Load all test scenarios into the benchmark.
    
    Args:
        benchmark: RAGBenchmark instance to load tests into
    """
    create_debate_test_cases(benchmark)
    create_role_reversal_test_cases(benchmark)  # CRITICAL for ATLAS
    create_chat_test_cases(benchmark)
    create_ocr_test_cases(benchmark)
    create_edge_case_test_cases(benchmark)
    
    print(f"✅ Loaded {len(benchmark.test_cases)} test scenarios")
    print(f"   - Debate tests: 5")
    print(f"   - Role Reversal tests: 2 (CRITICAL)")
    print(f"   - Chat tests: 2")
    print(f"   - OCR tests: 2")
    print(f"   - Edge case tests: 2")


if __name__ == "__main__":
    print("✅ RAG Test Scenarios module loaded successfully")
    print("These scenarios will be loaded by run_rag_benchmark.py")
