"""
Pinecone vector database search tool for internal dealflow insights.

This tool searches a Pinecone index containing internal dealflow data
that a fund has not made public, providing insights for briefs.

Index: "talipot" with namespaces "funds", "portfolio", "teams".

Embedding (pick one):
- OpenRouter (3072 dims): set OPENROUTER_API_KEY. Uses openai/text-embedding-3-large.
  Use this when your index was built with 3072-dim vectors.
- Local (384 dims): no extra key. Uses SentenceTransformer all-MiniLM-L6-v2.
  Use when the index was built with 384-dim vectors.
"""

import json
import os
from typing import Optional, List
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# Configuration: one Pinecone index with namespaces for funds, portfolio, teams
INDEX_NAME = "talipot"
NAMESPACES = ["funds", "portfolio", "teams"]

OPENROUTER_EMBEDDINGS_URL = "https://openrouter.ai/api/v1/embeddings"
# 3072-dim model on OpenRouter; must match how the index was built
OPENROUTER_EMBEDDING_MODEL = "openai/text-embedding-3-large"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_embedding_model = None


def _use_openrouter() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def _embed_with_openrouter(query: str) -> List[float]:
    """Get 3072-dim embedding via OpenRouter (no OpenAI key)."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    body = json.dumps({
        "model": os.getenv("PINECONE_OPENROUTER_EMBEDDING_MODEL", OPENROUTER_EMBEDDING_MODEL),
        "input": query,
    }).encode("utf-8")
    req = Request(
        OPENROUTER_EMBEDDINGS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"OpenRouter embeddings error {e.code}: {body}") from e
    except URLError as e:
        raise RuntimeError(f"OpenRouter request failed: {e}") from e
    emb = data.get("data", [{}])[0].get("embedding")
    if not emb:
        raise RuntimeError("OpenRouter response missing embedding")
    return emb


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(
            os.getenv("PINECONE_EMBEDDING_MODEL", EMBEDDING_MODEL)
        )
    return _embedding_model


def embed_query(query: str) -> List[float]:
    """Generate embedding: OpenRouter (3072 dims) if OPENROUTER_API_KEY set, else local (384 dims)."""
    if _use_openrouter():
        return _embed_with_openrouter(query)
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
        namespace: Which namespace to search ('funds', 'portfolio', 'teams', or None/'all' to search all three)
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
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        if INDEX_NAME not in existing_indexes:
            return f"**Error:** Index '{INDEX_NAME}' does not exist. Available indexes: {', '.join(existing_indexes) or 'none'}"
        
        index = pc.Index(INDEX_NAME)
        
        # Which namespaces to search
        if namespace and namespace in NAMESPACES:
            namespaces_to_search = [namespace]
        elif namespace in ("all", "all_indexes") or namespace is None:
            namespaces_to_search = NAMESPACES
        else:
            return f"**Error:** Invalid namespace '{namespace}'. Valid options: {', '.join(NAMESPACES)}, 'all', or None"
        
        query_vector = embed_query(query)
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
