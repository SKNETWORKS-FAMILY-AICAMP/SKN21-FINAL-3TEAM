"""
Qdrant Vector Store
"""
import uuid
from typing import List, Dict, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)


class QdrantVectorStore:
    """Qdrant 벡터 저장소"""

    def __init__(self, url: str, api_key: str, collection_name: str = "documents"):
        """
        Args:
            url: Qdrant 클라우드 URL
            api_key: Qdrant API 키
            collection_name: 컬렉션 이름
        """
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.client = None

    def initialize(self, vector_size: int = 768):
        """Qdrant 클라이언트 + 컬렉션 초기화

        Args:
            vector_size: 임베딩 벡터 차원 (jhgan/ko-sbert-nli = 768)
        """
        self.client = QdrantClient(url=self.url, api_key=self.api_key)

        # 컬렉션이 없으면 생성
        collections = self.client.get_collections().collections
        collection_exists = any(c.name == self.collection_name for c in collections)

        if not collection_exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            print(f"Collection '{self.collection_name}' created.")
        else:
            print(f"Collection '{self.collection_name}' already exists.")

        # 페이로드 인덱스 생성 (필터 검색용, 이미 있으면 무시)
        from qdrant_client.models import PayloadSchemaType
        for field, schema in [
            ("source", PayloadSchemaType.KEYWORD),
            ("doc_type", PayloadSchemaType.KEYWORD),
            ("document_id", PayloadSchemaType.INTEGER),
            ("scope", PayloadSchemaType.KEYWORD),
        ]:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=schema,
                )
            except Exception:
                pass  # 이미 존재하면 무시

        return self

    def add_documents(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: Optional[List[str]] = None,
    ):
        """문서 + 임베딩 + 메타데이터 저장

        Args:
            documents: 문서 텍스트 리스트
            embeddings: 임베딩 벡터 리스트
            metadatas: 메타데이터 리스트 (source, title, user_id, scope 등)
            ids: 문서 ID 리스트 (없으면 자동 생성)
        """
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]

        # numpy 배열을 list로 변환
        embeddings = [
            emb.tolist() if hasattr(emb, "tolist") else emb
            for emb in embeddings
        ]

        # PointStruct 생성
        points = []
        for i, (doc_id, doc, emb, meta) in enumerate(zip(ids, documents, embeddings, metadatas)):
            payload = {
                "content": doc,
                **meta,  # source, title, user_id, scope 등
            }
            points.append(
                PointStruct(
                    id=doc_id,
                    vector=emb,
                    payload=payload,
                )
            )

        # Qdrant에 저장
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        print(f"Added {len(points)} documents to Qdrant.")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 15,
        filter: Optional[Dict] = None,  # HybridSearcher 호환을 위해 filter로 변경
    ) -> List[Dict]:
        """벡터 유사도 검색

        Args:
            query_embedding: 쿼리 임베딩 벡터
            top_k: 반환할 상위 문서 수
            filter: 필터 조건 (예: {"scope": "company"})

        Returns:
            list of {"content", "source", "score", "doc_id", "title", ...}
        """
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        # numpy 배열이면 list로 변환
        if hasattr(query_embedding, "tolist"):
            query_embedding = query_embedding.tolist()

        # 필터 생성 (있으면)
        query_filter = None
        if filter:
            must_conditions = []
            must_not_conditions = []
            for key, value in filter.items():
                if key.endswith("__nin"):
                    # Not-In 필터: {"source__nin": ["documents", "meeting_minutes"]}
                    actual_key = key[:-5]
                    for v in value:
                        must_not_conditions.append(
                            FieldCondition(key=actual_key, match=MatchValue(value=v))
                        )
                else:
                    must_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
            query_filter = Filter(
                must=must_conditions or None,
                must_not=must_not_conditions or None,
            )

        # 검색 (qdrant-client 최신 버전)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k,
            query_filter=query_filter,
        ).points

        # 결과 포맷팅
        output = []
        for hit in results:
            output.append({
                "content": hit.payload.get("content", ""),
                "source": hit.payload.get("source", ""),
                "title": hit.payload.get("title", ""),
                "score": hit.score,
                "doc_id": hit.id,
                **{k: v for k, v in hit.payload.items() if k not in ["content", "source", "title"]},
            })

        return output

    def get_all_documents(self) -> Dict:
        """전체 문서 반환 (BM25 인덱스 구축용)

        Returns:
            {"ids": [...], "documents": [...], "metadatas": [...]}
        """
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        # Qdrant scroll로 전체 문서 가져오기
        all_points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=10000,  # 최대 10000개
            with_payload=True,
            with_vectors=False,
        )

        ids = [str(point.id) for point in all_points]
        documents = [point.payload.get("content", "") for point in all_points]
        metadatas = [
            {k: v for k, v in point.payload.items() if k != "content"}
            for point in all_points
        ]

        return {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }

    def list_documents_by_source(self, source: str, user_id: int = None, max_docs: int = 50) -> list[dict]:
        """source 필터로 Qdrant에 저장된 고유 문서 목록 반환 (title + document_id)

        Args:
            source: 메타데이터 source 값 (예: "documents")
            user_id: 사용자 ID — company 문서 + 해당 유저의 personal 문서 포함
            max_docs: 반환할 최대 문서 수 (기본 50, 0이면 무제한)
        Returns:
            [{"document_id": int, "title": str}, ...]  (document_id 기준 중복 제거)
        """
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        query_filter = Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source))]
        )

        # offset 기반 페이지네이션으로 전체 포인트 수집
        seen_ids = set()
        result = []
        offset = None

        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:
                doc_id = point.payload.get("document_id")
                title = point.payload.get("title", "제목 없음")
                scope = point.payload.get("scope", "company")
                uid = point.payload.get("user_id")

                # scope 필터: company는 모두 노출, personal은 본인 것만
                if scope == "personal":
                    if user_id is None or str(uid) != str(user_id):
                        continue

                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    result.append({"document_id": doc_id, "title": title})
                    if max_docs and len(result) >= max_docs:
                        return result

            if next_offset is None:
                break
            offset = next_offset

        return result

    def get_chunks_by_document_id(self, document_id: int) -> list[str]:
        """document_id로 Qdrant 청크 전체 수집 (순서대로 content 반환)

        Args:
            document_id: DB Document.id 값
        Returns:
            청크 content 리스트 (삽입 순서대로)
        """
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        query_filter = Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
        )

        all_points = []
        offset = None
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_points.extend(points)
            if next_offset is None:
                break
            offset = next_offset

        return [p.payload.get("content", "") for p in all_points if p.payload.get("content")]

    def delete_by_filter(self, filter_dict: dict):
        """메타데이터 필터 조건에 맞는 포인트 삭제"""
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")
        conditions = [
            FieldCondition(key=k, match=MatchValue(value=v))
            for k, v in filter_dict.items()
        ]
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(filter=Filter(must=conditions)),
        )

    def delete_collection(self):
        """컬렉션 삭제"""
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        self.client.delete_collection(self.collection_name)
        print(f"Collection '{self.collection_name}' deleted.")

    def count(self) -> int:
        """컬렉션의 문서 개수 반환"""
        if self.client is None:
            raise RuntimeError("QdrantVectorStore가 초기화되지 않았습니다.")

        collection_info = self.client.get_collection(self.collection_name)
        return collection_info.points_count
