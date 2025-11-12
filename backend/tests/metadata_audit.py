"""
Metadata Audit Tool - Check availability and quality of metadata fields
Analyzes: recency_score, authority_score, source, timestamp coverage
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from memory.vector_store import VectorStore
from datetime import datetime
import statistics

def audit_metadata(vector_store=None):
    """Audit metadata coverage and quality across document collection"""
    
    print("\n" + "="*70)
    print("METADATA AVAILABILITY AUDIT")
    print("="*70)
    
    # Initialize vector store
    if vector_store is None:
        print("\nInitializing vector store...")
        vector_store = VectorStore()
    
    # Get all documents with metadata
    print("Fetching all documents...")
    
    # Determine backend type
    if hasattr(vector_store, 'collection') and vector_store.collection is not None:
        # ChromaDB backend
        print("Using ChromaDB backend")
        collection = vector_store.collection
        results = collection.get(include=['metadatas', 'documents'])
        total_docs = len(results['ids'])
        metadatas = results['metadatas']
    elif hasattr(vector_store, 'lexical_metadata'):
        # FAISS backend - get metadata from lexical_metadata dict
        print("Using FAISS backend")
        metadatas = list(vector_store.lexical_metadata.values())
        total_docs = len(metadatas)
    else:
        print("\nNo valid backend found!")
        print(f"Has collection: {hasattr(vector_store, 'collection')}")
        print(f"Has lexical_metadata: {hasattr(vector_store, 'lexical_metadata')}")
        return
    
    print(f"Total documents: {total_docs}")
    
    if total_docs == 0:
        print("\nNo documents found in collection!")
        return
    
    # Analyze metadata fields
    metadata_fields = {
        'recency_score': [],
        'authority_score': [],
        'source': [],
        'timestamp': [],
        'conversation_id': [],
        'message_id': [],
        'role': []
    }
    
    missing_counts = {field: 0 for field in metadata_fields.keys()}
    
    print("\nAnalyzing metadata fields...")
    for i, metadata in enumerate(metadatas):
        for field in metadata_fields.keys():
            if field in metadata and metadata[field] is not None:
                value = metadata[field]
                # Skip empty strings
                if isinstance(value, str) and value.strip() == '':
                    missing_counts[field] += 1
                else:
                    metadata_fields[field].append(value)
            else:
                missing_counts[field] += 1
    
    # Print coverage summary
    print("\n" + "-"*70)
    print("METADATA COVERAGE SUMMARY")
    print("-"*70)
    print(f"{'Field':<20} {'Present':<10} {'Missing':<10} {'Coverage':<10}")
    print("-"*70)
    
    for field in metadata_fields.keys():
        present = len(metadata_fields[field])
        missing = missing_counts[field]
        coverage = (present / total_docs * 100) if total_docs > 0 else 0
        print(f"{field:<20} {present:<10} {missing:<10} {coverage:>6.1f}%")
    
    # Analyze recency_score distribution
    print("\n" + "-"*70)
    print("RECENCY SCORE ANALYSIS")
    print("-"*70)
    
    if metadata_fields['recency_score']:
        recency_scores = [float(s) for s in metadata_fields['recency_score'] if s is not None]
        print(f"Count:     {len(recency_scores)}")
        print(f"Min:       {min(recency_scores):.4f}")
        print(f"Max:       {max(recency_scores):.4f}")
        print(f"Mean:      {statistics.mean(recency_scores):.4f}")
        print(f"Median:    {statistics.median(recency_scores):.4f}")
        print(f"Std Dev:   {statistics.stdev(recency_scores) if len(recency_scores) > 1 else 0:.4f}")
        
        # Check if normalized (0-1 range)
        if min(recency_scores) >= 0 and max(recency_scores) <= 1:
            print("Status:    NORMALIZED (0-1 range)")
        else:
            print("Status:    NOT NORMALIZED - needs normalization!")
    else:
        print("NO RECENCY SCORES FOUND")
    
    # Analyze authority_score distribution
    print("\n" + "-"*70)
    print("AUTHORITY SCORE ANALYSIS")
    print("-"*70)
    
    if metadata_fields['authority_score']:
        authority_scores = [float(s) for s in metadata_fields['authority_score'] if s is not None]
        print(f"Count:     {len(authority_scores)}")
        print(f"Min:       {min(authority_scores):.4f}")
        print(f"Max:       {max(authority_scores):.4f}")
        print(f"Mean:      {statistics.mean(authority_scores):.4f}")
        print(f"Median:    {statistics.median(authority_scores):.4f}")
        print(f"Std Dev:   {statistics.stdev(authority_scores) if len(authority_scores) > 1 else 0:.4f}")
        
        # Check if normalized (0-1 range)
        if min(authority_scores) >= 0 and max(authority_scores) <= 1:
            print("Status:    NORMALIZED (0-1 range)")
        else:
            print("Status:    NOT NORMALIZED - needs normalization!")
    else:
        print("NO AUTHORITY SCORES FOUND")
    
    # Analyze timestamp distribution
    print("\n" + "-"*70)
    print("TIMESTAMP ANALYSIS")
    print("-"*70)
    
    if metadata_fields['timestamp']:
        timestamps = metadata_fields['timestamp']
        print(f"Count:     {len(timestamps)}")
        print(f"Sample timestamps (first 5):")
        for ts in timestamps[:5]:
            print(f"  - {ts}")
        
        # Try to parse timestamps
        try:
            parsed_dates = []
            for ts in timestamps:
                if isinstance(ts, str):
                    # Try ISO format
                    try:
                        parsed_dates.append(datetime.fromisoformat(ts.replace('Z', '+00:00')))
                    except:
                        pass
            
            if parsed_dates:
                print(f"Parseable: {len(parsed_dates)}/{len(timestamps)}")
                print(f"Oldest:    {min(parsed_dates).strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Newest:    {max(parsed_dates).strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("Status:    NO PARSEABLE TIMESTAMPS")
        except Exception as e:
            print(f"Error parsing timestamps: {e}")
    else:
        print("NO TIMESTAMPS FOUND")
    
    # Analyze source distribution
    print("\n" + "-"*70)
    print("SOURCE ANALYSIS")
    print("-"*70)
    
    if metadata_fields['source']:
        sources = metadata_fields['source']
        unique_sources = set(sources)
        print(f"Count:     {len(sources)}")
        print(f"Unique:    {len(unique_sources)}")
        print(f"Sources:   {', '.join(sorted(unique_sources)[:10])}")
        if len(unique_sources) > 10:
            print(f"           ... and {len(unique_sources) - 10} more")
    else:
        print("NO SOURCES FOUND")
    
    # RECOMMENDATION
    print("\n" + "="*70)
    print("RECOMMENDATION")
    print("="*70)
    
    recency_coverage = (len(metadata_fields['recency_score']) / total_docs * 100) if total_docs > 0 else 0
    authority_coverage = (len(metadata_fields['authority_score']) / total_docs * 100) if total_docs > 0 else 0
    
    if recency_coverage < 50 or authority_coverage < 50:
        print("\nSKIP Step 3 (Metadata Boost) - Insufficient metadata coverage")
        print(f"  Recency:   {recency_coverage:.1f}% (need >50%)")
        print(f"  Authority: {authority_coverage:.1f}% (need >50%)")
        print("\nPROCEED to Step 4 (HGB Soft Bias) - Metadata-independent approach")
    else:
        print("\nPROCEED with Step 3 (Metadata Boost) - Good metadata coverage")
        print(f"  Recency:   {recency_coverage:.1f}%")
        print(f"  Authority: {authority_coverage:.1f}%")
        
        # Check normalization
        needs_normalization = []
        if metadata_fields['recency_score']:
            recency_scores = [float(s) for s in metadata_fields['recency_score']]
            if not (min(recency_scores) >= 0 and max(recency_scores) <= 1):
                needs_normalization.append('recency_score')
        
        if metadata_fields['authority_score']:
            authority_scores = [float(s) for s in metadata_fields['authority_score']]
            if not (min(authority_scores) >= 0 and max(authority_scores) <= 1):
                needs_normalization.append('authority_score')
        
        if needs_normalization:
            print(f"\nWARNING: Fields need normalization: {', '.join(needs_normalization)}")
            print("         Implement min-max scaling before testing metadata boost")
    
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        audit_metadata()
    except Exception as e:
        print(f"\nError during audit: {e}")
        import traceback
        traceback.print_exc()
