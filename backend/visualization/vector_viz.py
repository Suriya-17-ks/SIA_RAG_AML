"""
Vector Visualization Module for ChromaDB Embeddings

This module provides utilities to visualize document chunks and query vectors
in 2D/3D space using dimensionality reduction techniques.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import plotly.graph_objects as go
import plotly.express as px
from sklearn.manifold import TSNE
from umap import UMAP
import pandas as pd
from backend.storage.chroma_client import ChromaStore


class VectorVisualizer:
    """Visualize vector embeddings and query similarity."""
    
    def __init__(self, chroma_store: ChromaStore):
        """
        Initialize visualizer with ChromaDB store.
        
        Args:
            chroma_store: ChromaStore instance
        """
        self.store = chroma_store
        self.collection = chroma_store.collection
    
    def get_all_embeddings_with_metadata(self, limit: int = 1000) -> Tuple[np.ndarray, List[Dict]]:
        """
        Retrieve all embeddings and metadata from ChromaDB.
        
        Args:
            limit: Maximum number of embeddings to retrieve
            
        Returns:
            Tuple of (embeddings array, metadata list)
        """
        # Get all items from collection
        results = self.collection.get(
            limit=limit,
            include=['embeddings', 'metadatas', 'documents']
        )
        
        embeddings = np.array(results['embeddings'])
        metadata = []
        
        for i, doc in enumerate(results['documents']):
            meta = results['metadatas'][i] if results['metadatas'] else {}
            metadata.append({
                'id': results['ids'][i],
                'content': doc[:100] + '...' if len(doc) > 100 else doc,  # Truncate for display
                'full_content': doc,
                'page': meta.get('page_number', 0),
                'section': meta.get('section_title', 'Unknown'),
                'type': meta.get('content_type', 'paragraph'),
                'doc_id': meta.get('doc_id', ''),
            })
        
        return embeddings, metadata
    
    def reduce_dimensions(
        self, 
        embeddings: np.ndarray, 
        method: str = 'umap',
        n_components: int = 2,
        random_state: int = 42
    ) -> np.ndarray:
        """
        Reduce embedding dimensions to 2D or 3D.
        
        Args:
            embeddings: High-dimensional embeddings
            method: 'umap' or 'tsne'
            n_components: 2 for 2D, 3 for 3D
            random_state: Random seed for reproducibility
            
        Returns:
            Reduced embeddings
        """
        if method.lower() == 'umap':
            reducer = UMAP(
                n_components=n_components,
                random_state=random_state,
                n_neighbors=15,
                min_dist=0.1,
                metric='cosine'
            )
        elif method.lower() == 'tsne':
            reducer = TSNE(
                n_components=n_components,
                random_state=random_state,
                perplexity=30,
                metric='cosine'
            )
        else:
            raise ValueError(f"Unknown method: {method}. Use 'umap' or 'tsne'")
        
        return reducer.fit_transform(embeddings)
    
    def visualize_vector_space(
        self,
        query: Optional[str] = None,
        method: str = 'umap',
        n_components: int = 2,
        limit: int = 500,
        top_k: int = 10
    ) -> go.Figure:
        """
        Create interactive 2D or 3D visualization of vector space.
        
        Args:
            query: Optional query to highlight similar chunks
            method: 'umap' or 'tsne'
            n_components: 2 or 3 dimensions
            limit: Max number of chunks to visualize
            top_k: Number of top results to highlight if query provided
            
        Returns:
            Plotly figure object
        """
        # Get all embeddings
        embeddings, metadata = self.get_all_embeddings_with_metadata(limit=limit)
        
        # Check for empty database FIRST before any processing
        if len(embeddings) == 0:
            raise ValueError(
                "No embeddings found in ChromaDB. Please upload documents first.\n\n"
                "To upload documents:\n"
                "1. Go to the main interface (index.html)\n"
                "2. Upload PDF files\n"
                "3. Wait for processing to complete\n"
                "4. Return here to visualize"
            )
        
        # Add query embedding if provided
        query_embedding = None
        query_results_ids = set()
        
        if query:
            # Get query embedding and similar chunks
            query_results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, len(embeddings)),  # Don't ask for more than available
                include=['embeddings', 'distances']
            )
            
            if query_results and query_results['embeddings'] and len(query_results['embeddings']) > 0:
                query_embedding = np.array(query_results['embeddings'][0])
                if query_results['ids'] and len(query_results['ids']) > 0:
                    query_results_ids = set(query_results['ids'][0])
                
                # Combine embeddings
                all_embeddings = np.vstack([embeddings, query_embedding])
            else:
                all_embeddings = embeddings
        else:
            all_embeddings = embeddings
        
        # Reduce dimensions
        reduced = self.reduce_dimensions(all_embeddings, method, n_components)
        
        # Separate query point from document chunks
        if query and query_embedding is not None:
            doc_reduced = reduced[:-1]
            query_reduced = reduced[-1:]
        else:
            doc_reduced = reduced
            query_reduced = None
        
        # Prepare data for plotting
        df = pd.DataFrame({
            'x': doc_reduced[:, 0],
            'y': doc_reduced[:, 1],
            'content': [m['content'] for m in metadata],
            'page': [m['page'] for m in metadata],
            'section': [m['section'] for m in metadata],
            'type': [m['type'] for m in metadata],
            'doc_id': [m['doc_id'] for m in metadata],
            'is_relevant': [m['id'] in query_results_ids for m in metadata]
        })
        
        if n_components == 3:
            df['z'] = doc_reduced[:, 2]
        
        # Create figure
        if n_components == 2:
            fig = self._create_2d_plot(df, query_reduced, query)
        else:
            fig = self._create_3d_plot(df, query_reduced, query)
        
        return fig
    
    def _create_2d_plot(
        self, 
        df: pd.DataFrame, 
        query_point: Optional[np.ndarray],
        query_text: Optional[str]
    ) -> go.Figure:
        """Create 2D scatter plot."""
        fig = go.Figure()
        
        # Plot non-relevant chunks
        non_relevant = df[~df['is_relevant']]
        if len(non_relevant) > 0:
            fig.add_trace(go.Scatter(
                x=non_relevant['x'],
                y=non_relevant['y'],
                mode='markers',
                marker=dict(
                    size=8,
                    color='lightblue',
                    opacity=0.6,
                    line=dict(width=0.5, color='white')
                ),
                text=non_relevant['content'],
                customdata=np.column_stack((
                    non_relevant['page'], 
                    non_relevant['section'],
                    non_relevant['type'],
                    non_relevant['doc_id']
                )),
                hovertemplate='<b>Content:</b> %{text}<br>' +
                              '<b>Page:</b> %{customdata[0]}<br>' +
                              '<b>Section:</b> %{customdata[1]}<br>' +
                              '<b>Type:</b> %{customdata[2]}<br>' +
                              '<b>Doc ID:</b> %{customdata[3]}<extra></extra>',
                name='Document Chunks'
            ))
        
        # Plot relevant chunks (highlighted)
        relevant = df[df['is_relevant']]
        if len(relevant) > 0:
            fig.add_trace(go.Scatter(
                x=relevant['x'],
                y=relevant['y'],
                mode='markers',
                marker=dict(
                    size=12,
                    color='orange',
                    opacity=0.9,
                    line=dict(width=2, color='red'),
                    symbol='star'
                ),
                text=relevant['content'],
                customdata=np.column_stack((
                    relevant['page'], 
                    relevant['section'],
                    relevant['type'],
                    relevant['doc_id']
                )),
                hovertemplate='<b>⭐ RELEVANT</b><br>' +
                              '<b>Content:</b> %{text}<br>' +
                              '<b>Page:</b> %{customdata[0]}<br>' +
                              '<b>Section:</b> %{customdata[1]}<br>' +
                              '<b>Type:</b> %{customdata[2]}<br>' +
                              '<b>Doc ID:</b> %{customdata[3]}<extra></extra>',
                name='Relevant to Query'
            ))
        
        # Plot query point
        if query_point is not None:
            fig.add_trace(go.Scatter(
                x=[query_point[0, 0]],
                y=[query_point[0, 1]],
                mode='markers+text',
                marker=dict(
                    size=16,
                    color='red',
                    symbol='diamond',
                    line=dict(width=2, color='darkred')
                ),
                text=['QUERY'],
                textposition='top center',
                hovertemplate=f'<b>Query:</b> {query_text}<extra></extra>',
                name='Your Query'
            ))
        
        fig.update_layout(
            title=dict(
                text='Document Vector Space Visualization' + (f'<br><sub>Query: "{query_text}"</sub>' if query_text else ''),
                x=0.5,
                xanchor='center'
            ),
            xaxis_title='Dimension 1',
            yaxis_title='Dimension 2',
            hovermode='closest',
            template='plotly_white',
            width=1000,
            height=700,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )
        
        return fig
    
    def _create_3d_plot(
        self, 
        df: pd.DataFrame, 
        query_point: Optional[np.ndarray],
        query_text: Optional[str]
    ) -> go.Figure:
        """Create 3D scatter plot."""
        fig = go.Figure()
        
        # Plot non-relevant chunks
        non_relevant = df[~df['is_relevant']]
        if len(non_relevant) > 0:
            fig.add_trace(go.Scatter3d(
                x=non_relevant['x'],
                y=non_relevant['y'],
                z=non_relevant['z'],
                mode='markers',
                marker=dict(
                    size=5,
                    color='lightblue',
                    opacity=0.6
                ),
                text=non_relevant['content'],
                customdata=np.column_stack((
                    non_relevant['page'], 
                    non_relevant['section'],
                    non_relevant['type']
                )),
                hovertemplate='<b>Content:</b> %{text}<br>' +
                              '<b>Page:</b> %{customdata[0]}<br>' +
                              '<b>Section:</b> %{customdata[1]}<br>' +
                              '<b>Type:</b> %{customdata[2]}<extra></extra>',
                name='Document Chunks'
            ))
        
        # Plot relevant chunks
        relevant = df[df['is_relevant']]
        if len(relevant) > 0:
            fig.add_trace(go.Scatter3d(
                x=relevant['x'],
                y=relevant['y'],
                z=relevant['z'],
                mode='markers',
                marker=dict(
                    size=8,
                    color='orange',
                    opacity=0.9,
                    symbol='diamond'
                ),
                text=relevant['content'],
                customdata=np.column_stack((
                    relevant['page'], 
                    relevant['section'],
                    relevant['type']
                )),
                hovertemplate='<b>⭐ RELEVANT</b><br>' +
                              '<b>Content:</b> %{text}<br>' +
                              '<b>Page:</b> %{customdata[0]}<br>' +
                              '<b>Section:</b> %{customdata[1]}<br>' +
                              '<b>Type:</b> %{customdata[2]}<extra></extra>',
                name='Relevant to Query'
            ))
        
        # Plot query point
        if query_point is not None:
            fig.add_trace(go.Scatter3d(
                x=[query_point[0, 0]],
                y=[query_point[0, 1]],
                z=[query_point[0, 2]],
                mode='markers+text',
                marker=dict(
                    size=10,
                    color='red',
                    symbol='diamond'
                ),
                text=['QUERY'],
                textposition='top center',
                hovertemplate=f'<b>Query:</b> {query_text}<extra></extra>',
                name='Your Query'
            ))
        
        fig.update_layout(
            title=f'3D Vector Space' + (f'<br><sub>Query: "{query_text}"</sub>' if query_text else ''),
            scene=dict(
                xaxis_title='Dimension 1',
                yaxis_title='Dimension 2',
                zaxis_title='Dimension 3'
            ),
            hovermode='closest',
            template='plotly_white',
            width=1000,
            height=700
        )
        
        return fig
    
    def create_similarity_heatmap(
        self,
        query: str,
        top_k: int = 20
    ) -> go.Figure:
        """
        Create a heatmap showing similarity scores.
        
        Args:
            query: Query text
            top_k: Number of top results to show
            
        Returns:
            Plotly heatmap figure
        """
        # Get query results with distances
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        if not results or not results['documents'][0]:
            raise ValueError("No results found for query")
        
        # Extract data
        documents = results['documents'][0]
        distances = results['distances'][0]
        metadatas = results['metadatas'][0]
        
        # Convert distance to similarity (cosine similarity = 1 - distance)
        similarities = [1 - d for d in distances]
        
        # Prepare labels
        labels = [
            f"Page {m.get('page_number', 'N/A')}: {doc[:50]}..."
            for doc, m in zip(documents, metadatas)
        ]
        
        # Create heatmap data
        heatmap_data = [[sim] for sim in similarities]
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data,
            y=labels,
            x=['Similarity'],
            colorscale='RdYlGn',
            text=[[f'{sim:.3f}'] for sim in similarities],
            texttemplate='%{text}',
            textfont={"size": 10},
            colorbar=dict(title="Similarity Score")
        ))
        
        fig.update_layout(
            title=f'Similarity Scores for Query: "{query}"',
            xaxis_title='',
            yaxis_title='Document Chunks (Ranked)',
            height=max(400, top_k * 30),
            template='plotly_white'
        )
        
        return fig
    
    def export_visualization(
        self,
        fig: go.Figure,
        filename: str = 'vector_visualization.html'
    ):
        """
        Export visualization to interactive HTML file.
        
        Args:
            fig: Plotly figure
            filename: Output filename
        """
        fig.write_html(filename)
        print(f"Visualization saved to {filename}")


def visualize_query_similarity(
    query: str,
    granularity: str = "micro",
    method: str = "umap",
    n_components: int = 2,
    top_k: int = 10,
    limit: int = 500
) -> Tuple[go.Figure, go.Figure]:
    """
    Convenience function to visualize query similarity.
    
    Args:
        query: Query text
        granularity: "micro" or "macro"
        method: "umap" or "tsne"
        n_components: 2 or 3
        top_k: Number of similar chunks to highlight
        limit: Max chunks to visualize
        
    Returns:
        Tuple of (vector_space_fig, heatmap_fig)
    """
    store = ChromaStore(granularity=granularity)
    viz = VectorVisualizer(store)
    
    # Create vector space visualization
    space_fig = viz.visualize_vector_space(
        query=query,
        method=method,
        n_components=n_components,
        limit=limit,
        top_k=top_k
    )
    
    # Create similarity heatmap
    heatmap_fig = viz.create_similarity_heatmap(query, top_k)
    
    return space_fig, heatmap_fig
