"""
API endpoints for vector visualization
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from typing import Optional
from backend.visualization.vector_viz import VectorVisualizer, visualize_query_similarity
from backend.storage.chroma_client import ChromaStore
import plotly

router = APIRouter()


@router.get("/vector-space")
async def get_vector_space_visualization(
    query: Optional[str] = Query(None, description="Query text to highlight similar chunks"),
    granularity: str = Query("micro", description="micro or macro"),
    method: str = Query("umap", description="umap or tsne"),
    dimensions: int = Query(2, description="2 or 3 for 2D/3D visualization"),
    top_k: int = Query(10, description="Number of similar chunks to highlight"),
    limit: int = Query(500, description="Max chunks to visualize")
):
    """
    Get vector space visualization data.
    Returns HTML with interactive Plotly visualization.
    """
    try:
        store = ChromaStore(granularity=granularity)
        
        # Check if there are any documents
        if store.count() == 0:
            raise HTTPException(
                status_code=404,
                detail="No documents found in ChromaDB. Please upload PDFs first."
            )
        
        viz = VectorVisualizer(store)
        
        fig = viz.visualize_vector_space(
            query=query,
            method=method,
            n_components=dimensions,
            limit=limit,
            top_k=top_k
        )
        
        # Convert to HTML
        html = fig.to_html(include_plotlyjs='cdn')
        
        return HTMLResponse(content=html)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Visualization error: {str(e)}")


@router.get("/similarity-heatmap")
async def get_similarity_heatmap(
    query: str = Query(..., description="Query text"),
    granularity: str = Query("micro", description="micro or macro"),
    top_k: int = Query(20, description="Number of results to show")
):
    """
    Get similarity heatmap for a query.
    Returns HTML with interactive Plotly heatmap.
    """
    try:
        store = ChromaStore(granularity=granularity)
        
        if store.count() == 0:
            raise HTTPException(
                status_code=404,
                detail="No documents found in ChromaDB. Please upload PDFs first."
            )
        
        viz = VectorVisualizer(store)
        fig = viz.create_similarity_heatmap(query, top_k)
        
        # Convert to HTML
        html = fig.to_html(include_plotlyjs='cdn')
        
        return HTMLResponse(content=html)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heatmap error: {str(e)}")


@router.get("/visualization-data")
async def get_visualization_data(
    query: str = Query(..., description="Query text"),
    granularity: str = Query("micro", description="micro or macro"),
    method: str = Query("umap", description="umap or tsne"),
    top_k: int = Query(10, description="Number of similar chunks"),
    limit: int = Query(500, description="Max chunks to visualize")
):
    """
    Get raw visualization data as JSON (for custom frontend rendering).
    """
    try:
        store = ChromaStore(granularity=granularity)
        viz = VectorVisualizer(store)
        
        # Get embeddings and reduce dimensions
        embeddings, metadata = viz.get_all_embeddings_with_metadata(limit=limit)
        
        if len(embeddings) == 0:
            raise HTTPException(status_code=404, detail="No embeddings found")
        
        # Get query results
        query_results = store.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=['embeddings', 'distances', 'documents']
        )
        
        # Reduce dimensions
        import numpy as np
        query_embedding = np.array(query_results['embeddings'][0])
        all_embeddings = np.vstack([embeddings, query_embedding])
        reduced = viz.reduce_dimensions(all_embeddings, method, n_components=2)
        
        # Prepare response
        doc_points = reduced[:-1]
        query_point = reduced[-1]
        
        relevant_ids = set(query_results['ids'][0])
        
        return {
            "document_points": [
                {
                    "x": float(doc_points[i, 0]),
                    "y": float(doc_points[i, 1]),
                    "content": metadata[i]['content'],
                    "page": metadata[i]['page'],
                    "section": metadata[i]['section'],
                    "type": metadata[i]['type'],
                    "is_relevant": metadata[i]['id'] in relevant_ids
                }
                for i in range(len(metadata))
            ],
            "query_point": {
                "x": float(query_point[0]),
                "y": float(query_point[1]),
                "text": query
            },
            "similarity_scores": [
                {
                    "content": query_results['documents'][0][i][:100],
                    "similarity": 1 - query_results['distances'][0][i],
                    "distance": query_results['distances'][0][i]
                }
                for i in range(len(query_results['documents'][0]))
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_collection_stats(
    granularity: str = Query("micro", description="micro or macro")
):
    """Get statistics about the vector collection."""
    try:
        store = ChromaStore(granularity=granularity)
        
        return {
            "collection_name": store.collection_name,
            "total_chunks": store.count(),
            "granularity": granularity,
            "embedding_model": store.collection.metadata.get("embedding_function", "unknown")
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
