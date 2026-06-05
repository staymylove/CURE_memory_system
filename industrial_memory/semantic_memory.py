"""
Industrial Memory System - Phase 2: 向量检索层（RAG）

实现语义记忆和智能检索
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from dataclasses import dataclass
import json
import faiss
import pickle
from pathlib import Path


@dataclass
class SemanticMemoryItem:
    """语义记忆条目"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None


class EmbeddingModel:
    """嵌入模型接口"""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name
        self.dimension = 1536  # OpenAI embedding dimension

    async def encode(self, text: str) -> np.ndarray:
        """
        将文本编码为向量

        实际使用时替换为：
        - OpenAI API
        - HuggingFace模型
        - 本地Sentence Transformers
        """
        # Mock实现 - 生成随机向量用于演示
        # 实际应该调用真实的embedding API
        return np.random.randn(self.dimension).astype('float32')

    async def encode_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码"""
        embeddings = []
        for text in texts:
            emb = await self.encode(text)
            embeddings.append(emb)
        return np.array(embeddings)


class VectorStore:
    """向量存储基类"""

    def add(
        self,
        ids: List[str],
        vectors: np.ndarray,
        metadata: List[Dict]
    ) -> None:
        """添加向量"""
        raise NotImplementedError

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """搜索最相似的向量"""
        raise NotImplementedError

    def delete(self, ids: List[str]) -> None:
        """删除向量"""
        raise NotImplementedError

    def save(self, path: str) -> None:
        """保存索引"""
        raise NotImplementedError

    def load(self, path: str) -> None:
        """加载索引"""
        raise NotImplementedError


class FAISSVectorStore(VectorStore):
    """FAISS向量存储 - 本地高性能"""

    def __init__(self, dimension: int = 1536, index_type: str = "flat"):
        """
        index_type:
        - flat: 精确搜索（小数据集）
        - ivf: 倒排索引（大数据集）
        - hnsw: 层次导航（平衡性能和精度）
        """
        self.dimension = dimension
        self.index_type = index_type

        # 创建索引
        if index_type == "flat":
            self.index = faiss.IndexFlatL2(dimension)
        elif index_type == "ivf":
            # IVF需要训练
            quantizer = faiss.IndexFlatL2(dimension)
            self.index = faiss.IndexIVFFlat(quantizer, dimension, 100)
        elif index_type == "hnsw":
            self.index = faiss.IndexHNSWFlat(dimension, 32)
        else:
            raise ValueError(f"Unknown index type: {index_type}")

        # 元数据存储（FAISS不存储元数据）
        self.id_to_metadata: Dict[str, Dict] = {}
        self.id_to_index: Dict[str, int] = {}
        self.index_to_id: Dict[int, str] = {}
        self.next_index = 0

    def add(
        self,
        ids: List[str],
        vectors: np.ndarray,
        metadata: List[Dict]
    ) -> None:
        """添加向量"""
        # 确保向量是float32
        vectors = vectors.astype('float32')

        # 如果是IVF且未训练，先训练
        if self.index_type == "ivf" and not self.index.is_trained:
            self.index.train(vectors)

        # 添加到FAISS
        self.index.add(vectors)

        # 保存元数据映射
        for i, (id_, meta) in enumerate(zip(ids, metadata)):
            idx = self.next_index + i
            self.id_to_metadata[id_] = meta
            self.id_to_index[id_] = idx
            self.index_to_id[idx] = id_

        self.next_index += len(ids)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """搜索"""
        query_vector = query_vector.astype('float32').reshape(1, -1)

        # 搜索更多结果用于过滤
        search_k = top_k * 3 if filters else top_k
        distances, indices = self.index.search(query_vector, search_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS返回-1表示没有更多结果
                continue

            id_ = self.index_to_id.get(idx)
            if not id_:
                continue

            metadata = self.id_to_metadata.get(id_, {})

            # 应用过滤器
            if filters:
                match = all(
                    metadata.get(k) == v
                    for k, v in filters.items()
                )
                if not match:
                    continue

            results.append((id_, float(dist), metadata))

            if len(results) >= top_k:
                break

        return results

    def delete(self, ids: List[str]) -> None:
        """删除向量（FAISS不支持直接删除，需要重建索引）"""
        # 收集要保留的向量
        keep_ids = [
            id_ for id_ in self.id_to_metadata.keys()
            if id_ not in ids
        ]

        if not keep_ids:
            # 清空
            self.__init__(self.dimension, self.index_type)
            return

        # 重建索引
        keep_indices = [self.id_to_index[id_] for id_ in keep_ids]
        keep_vectors = []

        for idx in keep_indices:
            # 从索引中提取向量（FAISS特定操作）
            vector = self.index.reconstruct(idx)
            keep_vectors.append(vector)

        keep_metadata = [self.id_to_metadata[id_] for id_ in keep_ids]

        # 重建
        self.__init__(self.dimension, self.index_type)
        self.add(keep_ids, np.array(keep_vectors), keep_metadata)

    def save(self, path: str) -> None:
        """保存索引"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # 保存FAISS索引
        faiss.write_index(self.index, str(path / "index.faiss"))

        # 保存元数据
        metadata = {
            'id_to_metadata': self.id_to_metadata,
            'id_to_index': self.id_to_index,
            'index_to_id': self.index_to_id,
            'next_index': self.next_index,
            'dimension': self.dimension,
            'index_type': self.index_type
        }

        with open(path / "metadata.pkl", 'wb') as f:
            pickle.dump(metadata, f)

    def load(self, path: str) -> None:
        """加载索引"""
        path = Path(path)

        # 加载FAISS索引
        self.index = faiss.read_index(str(path / "index.faiss"))

        # 加载元数据
        with open(path / "metadata.pkl", 'rb') as f:
            metadata = pickle.load(f)

        self.id_to_metadata = metadata['id_to_metadata']
        self.id_to_index = metadata['id_to_index']
        self.index_to_id = metadata['index_to_id']
        self.next_index = metadata['next_index']
        self.dimension = metadata['dimension']
        self.index_type = metadata['index_type']


class SemanticMemory:
    """语义记忆系统"""

    def __init__(
        self,
        embedding_model: Optional[EmbeddingModel] = None,
        vector_store: Optional[VectorStore] = None
    ):
        self.embedding_model = embedding_model or EmbeddingModel()
        self.vector_store = vector_store or FAISSVectorStore(
            dimension=self.embedding_model.dimension
        )

    async def add(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> None:
        """添加记忆"""
        # 生成embedding
        embedding = await self.embedding_model.encode(content)

        # 存储
        self.vector_store.add(
            ids=[id],
            vectors=embedding.reshape(1, -1),
            metadata=[metadata]
        )

    async def add_batch(
        self,
        ids: List[str],
        contents: List[str],
        metadata: List[Dict[str, Any]]
    ) -> None:
        """批量添加"""
        # 批量编码
        embeddings = await self.embedding_model.encode_batch(contents)

        # 批量存储
        self.vector_store.add(ids, embeddings, metadata)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """语义搜索"""
        # 查询编码
        query_embedding = await self.embedding_model.encode(query)

        # 搜索
        results = self.vector_store.search(
            query_vector=query_embedding,
            top_k=top_k,
            filters=filters
        )

        return results

    def delete(self, ids: List[str]) -> None:
        """删除记忆"""
        self.vector_store.delete(ids)

    def save(self, path: str) -> None:
        """保存"""
        self.vector_store.save(path)

    def load(self, path: str) -> None:
        """加载"""
        self.vector_store.load(path)


class HybridRetrieval:
    """混合检索 - 结合关键词和语义搜索"""

    def __init__(
        self,
        semantic_memory: SemanticMemory,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7
    ):
        self.semantic_memory = semantic_memory
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight

    async def search(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """混合搜索"""
        # 1. 语义搜索
        semantic_results = await self.semantic_memory.search(
            query=query,
            top_k=top_k * 2  # 获取更多候选
        )

        semantic_scores = {
            id_: 1.0 / (1.0 + dist)  # 距离转相似度
            for id_, dist, _ in semantic_results
        }

        # 2. 关键词搜索（BM25简化版）
        query_terms = set(query.lower().split())
        keyword_scores = {}

        for doc in documents:
            doc_id = doc['id']
            doc_text = doc['content'].lower()
            doc_terms = set(doc_text.split())

            # 简单的关键词匹配分数
            overlap = len(query_terms & doc_terms)
            keyword_scores[doc_id] = overlap / (len(query_terms) + 1e-6)

        # 3. 融合分数
        all_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())
        hybrid_scores = {}

        for doc_id in all_ids:
            semantic_score = semantic_scores.get(doc_id, 0.0)
            keyword_score = keyword_scores.get(doc_id, 0.0)

            hybrid_scores[doc_id] = (
                self.semantic_weight * semantic_score +
                self.keyword_weight * keyword_score
            )

        # 4. 排序返回
        sorted_ids = sorted(
            hybrid_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        results = []
        doc_dict = {doc['id']: doc for doc in documents}

        for doc_id, score in sorted_ids:
            if doc_id in doc_dict:
                result = doc_dict[doc_id].copy()
                result['score'] = score
                results.append(result)

        return results


# ============ 使用示例 ============

async def demo():
    """演示语义记忆"""
    print("=== Semantic Memory Demo ===\n")

    # 创建语义记忆
    semantic_memory = SemanticMemory()

    # 添加一些记忆
    memories = [
        {
            'id': 'mem_1',
            'content': 'User likes Python programming and machine learning',
            'metadata': {'type': 'preference', 'session': 'session_001'}
        },
        {
            'id': 'mem_2',
            'content': 'User asked about deep learning frameworks',
            'metadata': {'type': 'question', 'session': 'session_001'}
        },
        {
            'id': 'mem_3',
            'content': 'User is working on a NLP project using transformers',
            'metadata': {'type': 'context', 'session': 'session_002'}
        },
        {
            'id': 'mem_4',
            'content': 'User prefers PyTorch over TensorFlow',
            'metadata': {'type': 'preference', 'session': 'session_002'}
        },
    ]

    print("Adding memories...")
    await semantic_memory.add_batch(
        ids=[m['id'] for m in memories],
        contents=[m['content'] for m in memories],
        metadata=[m['metadata'] for m in memories]
    )
    print(f"Added {len(memories)} memories\n")

    # 语义搜索
    queries = [
        "What does the user like to code in?",
        "Tell me about the user's AI interests",
        "Which framework does the user prefer?"
    ]

    for query in queries:
        print(f"Query: {query}")
        results = await semantic_memory.search(query, top_k=2)

        for id_, distance, metadata in results:
            print(f"  - {id_} (distance: {distance:.4f})")
            print(f"    Type: {metadata['type']}, Session: {metadata['session']}")
        print()

    # 带过滤的搜索
    print("Filtered search (only preferences):")
    results = await semantic_memory.search(
        "user preferences",
        top_k=3,
        filters={'type': 'preference'}
    )
    for id_, distance, metadata in results:
        print(f"  - {id_} (distance: {distance:.4f})")
    print()

    # 保存和加载
    print("Saving index...")
    semantic_memory.save("./vector_store")
    print("Saved successfully\n")

    print("Loading index...")
    semantic_memory2 = SemanticMemory()
    semantic_memory2.load("./vector_store")
    print("Loaded successfully\n")

    # 验证加载
    print("Testing loaded index:")
    results = await semantic_memory2.search("Python", top_k=1)
    for id_, distance, metadata in results:
        print(f"  - {id_} (distance: {distance:.4f})")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
