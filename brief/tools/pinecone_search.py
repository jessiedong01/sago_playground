"""
Pinecone vector database search tool for internal dealflow insights.

This tool searches a Pinecone index containing internal dealflow data
that a fund has not made public, providing insights for briefs.
"""

import os
from typing import Optional, List, Dict, Any
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# Configuration constants
INDEX_NAME = "dealflow-index"  # Update this to match your actual index name
ALL_NAMESPACES = ["funds", "portfolio", "teams"]

# Global embedding model instance (lazy loaded)
_embedding_model = None


def _get_embedding_model():
    """Get or create the global embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        # Using a common general-purpose embedding model
        # You can change this to match what was used during ingestion
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def embed_query(query: str) -> List[float]:
    """
    Generate embedding vector for a query string.
    
    Args:
        query: Text query to embed
        
    Returns:
        List of floats representing the embedding vector
    """
    model = _get_embedding_model()
    embedding = model.encode(query, convert_to_numpy=True)
    return embedding.tolist()


def search_dealflow(
    query: str,
    namespace: Optional[str] = None,
    top_k: int = 5
) -> str:
    """
    Search Pinecone index for internal dealflow insights.
    
    Use this tool to find non-public dealflow information that might help
    with fund or company briefs. This searches internal data including:
    - Fund information and insights
    - Portfolio company details
    - Team information and relationships
    
    Args:
        query: Search query text describing what you're looking for
        namespace: Specific namespace to search ('funds', 'portfolio', 'teams', or None/'all' for all namespaces)
        top_k: Number of results to return per namespace (default: 5)
        
    Returns:
        Markdown-formatted search results with id, score, namespace, and metadata.
        Returns error message if search fails.
    """
    # Initialize Pinecone
    api_key = os.getenv('PINECONE_API_KEY')
    if not api_key:
        return "**Error:** PINECONE_API_KEY not found in environment variables. Please set it in your .env file."
    
    try:
        pc = Pinecone(api_key=api_key)
        
        # Check if index exists
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        if INDEX_NAME not in existing_indexes:
            return f"**Error:** Index '{INDEX_NAME}' does not exist. Available indexes: {', '.join(existing_indexes)}"
        
        index = pc.Index(INDEX_NAME)
        
        # Generate query embedding
        query_vector = embed_query(query)
        
        # Determine which namespaces to search
        if namespace and namespace in ALL_NAMESPACES:
            namespaces_to_search = [namespace]
        elif namespace == 'all' or namespace is None:
            namespaces_to_search = ALL_NAMESPACES
        else:
            return f"**Error:** Invalid namespace '{namespace}'. Valid options: {', '.join(ALL_NAMESPACES)}, 'all', or None"
        
        # Search each namespace
        all_results = []
        
        for ns in namespaces_to_search:
            try:
                response = index.query(
                    vector=query_vector,
                    top_k=top_k,
                    namespace=ns,
                    include_metadata=True
                )
                
                for match in response.matches:
                    all_results.append({
                        'id': match.id,
                        'score': match.score,
                        'namespace': ns,
                        'metadata': match.metadata or {}
                    })
            except Exception as e:
                # Continue with other namespaces if one fails
                all_results.append({
                    'id': f'error-{ns}',
                    'score': 0.0,
                    'namespace': ns,
                    'metadata': {'error': str(e)}
                })
        
        # Sort all results by score
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Format results as markdown
        if not all_results:
            return f"**No results found** for query: '{query}'"
        
        result_lines = [f"## Dealflow Search Results for: '{query}'"]
        result_lines.append(f"\nFound {len(all_results)} result(s) across {len(namespaces_to_search)} namespace(s).\n")
        
        for i, result in enumerate(all_results, 1):
            result_lines.append(f"### Result {i}")
            result_lines.append(f"- **ID:** {result['id']}")
            result_lines.append(f"- **Namespace:** {result['namespace']}")
            result_lines.append(f"- **Score:** {result['score']:.4f}")
            
            if 'error' in result.get('metadata', {}):
                result_lines.append(f"- **Error:** {result['metadata']['error']}")
            else:
                result_lines.append(f"- **Metadata:**")
                metadata = result['metadata']
                for key, value in metadata.items():
                    if isinstance(value, (str, int, float, bool)):
                        result_lines.append(f"  - {key}: {value}")
                    elif isinstance(value, list):
                        result_lines.append(f"  - {key}: {', '.join(str(v) for v in value)}")
                    else:
                        result_lines.append(f"  - {key}: {str(value)}")
            result_lines.append("")
        
        return "\n".join(result_lines)
        
    except Exception as e:
        return f"**Search Error:** {str(e)}"
