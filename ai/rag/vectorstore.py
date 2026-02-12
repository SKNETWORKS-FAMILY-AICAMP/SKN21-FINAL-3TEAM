"""
Vector DB (ChromaDB) 관리

Chunk 전략:
  - 규정 문서: 조항 단위
  - 회의록: 문단 단위
"""
import uuid

import chromadb


class VectorStore:
    """ChromaDB 벡터 저장소"""

    def __init__(self, persist_dir: str = "./chroma_db"):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None

    def initialize(self):
        """ChromaDB 클라이언트 + 컬렉션 초기화"""
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        return self

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
    ):
        """문서 + 임베딩 + 메타데이터 저장"""
        if self.collection is None:
            raise RuntimeError("VectorStore가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        # ChromaDB는 numpy 배열을 지원하지 않으므로 list로 변환
        if embeddings is not None:
            embeddings = [
                emb.tolist() if hasattr(emb, "tolist") else emb
                for emb in embeddings
            ]

        kwargs = {
            "documents": documents,
            "metadatas": metadatas,
            "ids": ids,
        }
        if embeddings is not None:
            kwargs["embeddings"] = embeddings

        self.collection.upsert(**kwargs)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 15,
        filter: dict | None = None,
    ) -> list[dict]:
        """벡터 유사도 검색 (scope 필터 지원)

        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 상위 문서 수
            filter: ChromaDB where 필터
                예: {"$or": [{"scope": "company"},
                             {"$and": [{"scope": "personal"}, {"user_id": user_id}]}]}

        Returns:
            list of {"content", "source", "score", "doc_id"}
        """
        if self.collection is None:
            raise RuntimeError("VectorStore가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")

        # numpy 배열이면 list로 변환
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        # n_results가 컬렉션 크기를 초과하면 ChromaDB 에러 발생 방지
        count = self.collection.count()
        if count == 0:
            return []
        n_results = min(top_k, count)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if filter is not None:
            kwargs["where"] = filter

        results = self.collection.query(**kwargs)

        output = []
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            # cosine distance → similarity score (0~1)
            score = 1.0 - distance
            output.append({
                "content": results["documents"][0][i],
                "source": results["metadatas"][0][i].get("source", ""),
                "score": score,
                "doc_id": results["ids"][0][i],
            })
        return output

    def get_all_documents(self) -> dict:
        """BM25 인덱스 구축용 전체 문서 반환

        Returns:
            {"ids": [...], "documents": [...], "metadatas": [...]}
        """
        if self.collection is None:
            raise RuntimeError("VectorStore가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")

        result = self.collection.get(include=["documents", "metadatas"])
        return {
            "ids": result["ids"],
            "documents": result["documents"],
            "metadatas": result["metadatas"],
        }

    def delete_collection(self):
        """컬렉션 삭제 (재구축용)"""
        if self.client is None:
            raise RuntimeError("VectorStore가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")

        self.client.delete_collection("documents")
        self.collection = None
