#!/usr/bin/env python3
"""
Initialize the RAG knowledge base with documents.
Run this script to load documents into the vector store.
"""

import os
import sys
from pathlib import Path

# Add app to path
sys.path.append(str(Path(__file__).parent.parent))

from app.rag.store import vector_store
from app.utils.logger import log

def initialize_knowledge_base():
    """Initialize the knowledge base with documents."""
    log.info("Initializing knowledge base...")
    
    # Load documents from knowledge_base directory
    kb_dir = Path(__file__).parent.parent / "data" / "knowledge_base"
    
    if not kb_dir.exists():
        log.warning(f"Knowledge base directory not found: {kb_dir}")
        log.info("Creating empty knowledge base directory...")
        kb_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a sample document
        sample_doc = kb_dir / "sample.md"
        with open(sample_doc, 'w') as f:
            f.write("""# Sample Knowledge Base Document

## Getting Started
This is a sample document to demonstrate the RAG functionality.

## Information
The FunctionGemma agent can search this knowledge base to answer questions.
""")
        log.info(f"Created sample document: {sample_doc}")
    
    # Load documents into vector store
    vector_store.load_from_directory(str(kb_dir), "*.md")
    
    # Print statistics
    count = vector_store.collection.count()
    log.info(f"Knowledge base initialized with {count} document chunks")
    
    # Test retrieval
    from app.rag.retriever import knowledge_retriever
    test_result = knowledge_retriever.retrieve_context("getting started", top_k=1)
    log.info("Test retrieval successful:")
    log.info(f"Result: {test_result[:200]}...")

def main():
    """Main entry point."""
    print("=" * 60)
    print("KNOWLEDGE BASE INITIALIZATION")
    print("=" * 60)
    
    try:
        initialize_knowledge_base()
        print("\n✅ Knowledge base initialized successfully!")
        print("\nYou can now:")
        print("1. Ask the agent questions about your documents")
        print("2. Use the search_knowledge_base tool")
        print("3. Add more documents to data/knowledge_base/")
        
    except Exception as e:
        print(f"\n❌ Error initializing knowledge base: {e}")
        log.error(f"Initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
