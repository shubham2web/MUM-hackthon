# Phase 3: Advanced Memory Features - Scaffolding Summary

This document describes the Phase 3 scaffolding for advanced memory features.

## What's Been Implemented (Scaffolding)

### 1. MongoDB Audit Logging (`backend/memory/mongo_audit.py`)

**Purpose**: Optional MongoDB integration for audit trails and analytics

**Features**:
- ✅ Connection management with fallback if unavailable
- ✅ Event logging (memory additions, role reversals, consistency checks)
- ✅ Debate session tracking
- ✅ Consistency alerts collection
- ✅ Query methods for history and statistics

**Collections**:
- `memory_events`: All memory operations with timestamps
- `debate_sessions`: Debate metadata and status
- `consistency_alerts`: Contradiction warnings

**Usage**:
```python
from memory.mongo_audit import get_audit_logger

audit = get_audit_logger()

# Log memory addition
audit.log_memory_addition(
    role="proponent",
    content="...",
    debate_id="debate_001"
)

# Get debate history
history = audit.get_debate_history("debate_001")

# Get statistics
stats = audit.get_stats()
```

**Configuration**:
Set in `.env`:
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=atlas_memory  # optional, defaults to atlas_memory
```

### 2. Diagnostics Endpoint (`/memory/diagnostics`)

**GET** `/memory/diagnostics`

Returns comprehensive system diagnostics:
```json
{
  "memory_usage": {
    "short_term_messages": 10,
    "short_term_window": 10,
    "rag_enabled": true
  },
  "long_term_memory": {
    "total_memories": 150,
    "backend": "chroma"
  },
  "audit_stats": {
    "enabled": true,
    "total_events": 300,
    "total_sessions": 5,
    "total_alerts": 3
  },
  "debate_context": {
    "current_debate_id": "debate_001",
    "turn_counter": 15
  },
  "timestamp": "2025-11-12T10:30:00"
}
```

### 3. Optimization Endpoint (`/memory/optimize`)

**POST** `/memory/optimize`

Body:
```json
{
  "operation": "truncate_low_value" | "deduplicate" | "compress",
  "threshold": 0.5
}
```

**Operations** (scaffolded, pending implementation):
- `truncate_low_value`: Remove memories below relevance threshold
- `deduplicate`: Remove duplicate/near-duplicate memories
- `compress`: Summarize old memories to save tokens

## Installation (Optional)

To enable MongoDB audit logging:

```bash
# Install pymongo
pip install pymongo

# Set environment variable
# In .env file:
MONGODB_URI=mongodb://localhost:27017
```

**Note**: System works without MongoDB - it's completely optional.

## Integration Points

### Memory Manager Integration

To integrate audit logging into `memory_manager.py`:

```python
from memory.mongo_audit import get_audit_logger

class HybridMemoryManager:
    def __init__(self, ...):
        # ... existing init code ...
        self.audit_logger = get_audit_logger()
    
    def add_interaction(self, role, content, metadata=None, store_in_rag=True):
        # ... existing code ...
        
        # Log to MongoDB if enabled
        self.audit_logger.log_memory_addition(
            role=role,
            content=content,
            metadata=metadata,
            debate_id=self.current_debate_id,
            memory_id=result.get('long_term')
        )
        
        return result
    
    def build_role_reversal_context(self, current_role, previous_role, ...):
        # ... existing code ...
        
        # Log role reversal
        self.audit_logger.log_role_reversal(
            current_role=current_role,
            previous_role=previous_role,
            debate_id=debate_id,
            previous_args_count=len(previous_args)
        )
        
        return context_payload
    
    def detect_memory_inconsistencies(self, role, new_statement, ...):
        # ... existing code ...
        
        # Log consistency check
        self.audit_logger.log_consistency_check(
            role=role,
            new_statement=new_statement,
            has_inconsistencies=result['has_inconsistencies'],
            consistency_score=result['consistency_score'],
            warnings=result['warnings'],
            debate_id=debate_id
        )
        
        return result
```

## Testing

### Test MongoDB Audit Logging

```python
# backend/tests/test_mongo_audit.py
import pytest
from memory.mongo_audit import MongoAuditLogger

def test_audit_logging():
    audit = MongoAuditLogger()
    
    if not audit.enabled:
        pytest.skip("MongoDB not available")
    
    # Test session logging
    audit.log_debate_session("test_debate_001", topic="Test Topic")
    
    # Test memory logging
    audit.log_memory_addition(
        role="proponent",
        content="Test argument",
        debate_id="test_debate_001"
    )
    
    # Get history
    history = audit.get_debate_history("test_debate_001")
    assert len(history) > 0
    
    # Get stats
    stats = audit.get_stats()
    assert stats['enabled'] == True
```

### Test Diagnostics Endpoint

```bash
curl http://localhost:8000/memory/diagnostics
```

### Test Optimization Endpoint

```bash
curl -X POST http://localhost:8000/memory/optimize \
  -H "Content-Type: application/json" \
  -d '{"operation": "truncate_low_value", "threshold": 0.5}'
```

## Phase 3 Completion Checklist

### ✅ Completed (Scaffolding)
- [x] MongoDB audit logger class
- [x] Connection management with fallback
- [x] Event logging methods
- [x] Query methods for history/stats
- [x] Diagnostics endpoint
- [x] Optimization endpoint (stubs)

### 🔄 Pending (Full Implementation)
- [ ] Integrate audit logging into `memory_manager.py`
- [ ] Implement `truncate_low_value` optimization
- [ ] Implement `deduplicate` optimization
- [ ] Implement `compress` (summarization) optimization
- [ ] NLI model for better contradiction detection
- [ ] Token usage tracking and reporting
- [ ] Memory value scoring algorithm
- [ ] Automatic memory pruning

## Phase 4 Preview

Phase 4 features (not yet started):
- Visual RAG retrieval hits on dashboard
- Episodic memory tagging (auto-classify by theme)
- Emotional tone awareness in bias auditing
- Self-healing memory (context pruning + summarization)
- Real-time memory analytics dashboard
- Export/import memory snapshots

## Usage Examples

### Example 1: Enable MongoDB Audit Logging

1. Install MongoDB locally or use cloud instance
2. Install pymongo: `pip install pymongo`
3. Configure `.env`:
   ```
   MONGODB_URI=mongodb://localhost:27017
   ```
4. Restart server - audit logging auto-enables

### Example 2: Check Diagnostics

```python
import requests

response = requests.get('http://localhost:8000/memory/diagnostics')
data = response.json()

print(f"Short-term: {data['memory_usage']['short_term_messages']} messages")
print(f"Long-term: {data['long_term_memory']['total_memories']} memories")

if 'audit_stats' in data:
    print(f"Audit events: {data['audit_stats']['total_events']}")
```

### Example 3: Optimize Memory

```python
import requests

# Remove low-value memories
response = requests.post(
    'http://localhost:8000/memory/optimize',
    json={
        "operation": "truncate_low_value",
        "threshold": 0.5
    }
)

result = response.json()
print(f"Removed: {result['items_removed']} memories")
```

## Notes

- MongoDB is **completely optional** - system works without it
- Audit logging has zero performance impact when disabled
- All optimization operations are safe (non-destructive previews available)
- Diagnostics endpoint is always available regardless of MongoDB

## Next Steps

To complete Phase 3:
1. Add audit logging calls to `memory_manager.py` methods
2. Implement optimization algorithms
3. Add NLI model for contradiction detection
4. Create memory value scoring system
5. Build automatic pruning logic
6. Add comprehensive tests

## Files Created/Modified

### Created:
- `backend/memory/mongo_audit.py` - MongoDB audit logger
- `RAG_PRD/PHASE3_SCAFFOLDING.md` - This document

### Modified:
- `backend/api/memory_routes.py` - Added `/diagnostics` and `/optimize` endpoints

### To Modify (for full Phase 3):
- `backend/memory/memory_manager.py` - Integrate audit logging
- `backend/requirements.txt` - Add pymongo as optional
