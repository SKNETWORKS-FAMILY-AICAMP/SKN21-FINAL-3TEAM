# Qdrant 기반 RAG Pipeline을 기본으로 사용
try:
    from ai.rag.qdrant_pipeline import QdrantRAGPipeline, get_qdrant_pipeline, reset_qdrant_pipeline
    __all__ = ["QdrantRAGPipeline", "get_qdrant_pipeline", "reset_qdrant_pipeline"]
except ImportError:
    pass

# ChromaDB 기반 RAG Pipeline (optional)
try:
    from ai.rag.pipeline import RAGPipeline, get_pipeline, reset_pipeline
    if "__all__" in dir():
        __all__.extend(["RAGPipeline", "get_pipeline", "reset_pipeline"])
    else:
        __all__ = ["RAGPipeline", "get_pipeline", "reset_pipeline"]
except ImportError:
    pass
