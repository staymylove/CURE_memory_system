"""
简化版语义记忆 - 不依赖FAISS，用于快速测试

使用简单的余弦相似度进行搜索
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from dataclasses import dataclass
import json
import pickle
from pathlib import Path


@dataclass
class SemanticMemoryItem:
    """语义记忆条目"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: np.ndarray


class SimpleVectorStore:
    """简单的向量存储 - 基于numpy的暴力搜索"""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.items: List[SemanticMemoryItem] = []

    def add(
        self,
        ids: List[str],
        vectors: np.ndarray,
        metadata: List[Dict]
    ) -> None:
        """添加向量"""
        for id_, vector, meta in zip(ids, vectors, metadata):
            item = SemanticMemoryItem(
                id=id_,
                content=meta.get('content', ''),
                metadata=meta,
                embedding=vector
            )
            self.items.append(item)

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """搜索最相似的向量"""
        if not self.items:
            return []

        # 计算余弦相似度
        scores = []
        for item in self.items:
            # 应用过滤器
            if filters:
                match = all(
                    item.metadata.get(k) == v
                    for k, v in filters.items()
                )
                if not match:
                    continue

            # 余弦相似度
            similarity = np.dot(query_vector, item.embedding) / (
                np.linalg.norm(query_vector) * np.linalg.norm(item.embedding) + 1e-8
            )
            scores.append((item.id, similarity, item.metadata))

        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def delete(self, ids: List[str]) -> None:
        """删除向量"""
        self.items = [item for item in self.items if item.id not in ids]

    def save(self, path: str) -> None:
        """保存"""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        with open(path / "simple_store.pkl", 'wb') as f:
            pickle.dump({
                'dimension': self.dimension,
                'items': self.items
            }, f)

    def load(self, path: str) -> None:
        """加载"""
        path = Path(path)
        with open(path / "simple_store.pkl", 'rb') as f:
            data = pickle.load(f)
            self.dimension = data['dimension']
            self.items = data['items']


class MockEmbeddingModel:
    """Mock Embedding模型 - 用于演示"""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._word_embeddings = {}

    async def encode(self, text: str) -> np.ndarray:
        """
        简单的embedding模拟
        实际使用时替换为真实模型
        """
        # 基于单词的简单embedding
        words = text.lower().split()

        # 为每个单词生成一个固定的向量
        word_vectors = []
        for word in words:
            if word not in self._word_embeddings:
                # 使用单词的hash生成确定性的向量
                np.random.seed(hash(word) % (2**32))
                self._word_embeddings[word] = np.random.randn(self.dimension)
            word_vectors.append(self._word_embeddings[word])

        if not word_vectors:
            return np.random.randn(self.dimension)

        # 平均所有单词向量
        embedding = np.mean(word_vectors, axis=0)
        # 归一化
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)

        return embedding.astype('float32')

    async def encode_batch(self, texts: List[str]) -> np.ndarray:
        """批量编码"""
        embeddings = []
        for text in texts:
            emb = await self.encode(text)
            embeddings.append(emb)
        return np.array(embeddings)


class SimpleSemanticMemory:
    """简化版语义记忆"""

    def __init__(
        self,
        embedding_model: Optional[MockEmbeddingModel] = None,
        vector_store: Optional[SimpleVectorStore] = None
    ):
        self.embedding_model = embedding_model or MockEmbeddingModel()
        self.vector_store = vector_store or SimpleVectorStore(
            dimension=self.embedding_model.dimension
        )

    async def add(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> None:
        """添加记忆"""
        embedding = await self.embedding_model.encode(content)
        metadata['content'] = content  # 保存内容用于显示

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
        embeddings = await self.embedding_model.encode_batch(contents)

        # 添加content到metadata
        for meta, content in zip(metadata, contents):
            meta['content'] = content

        self.vector_store.add(ids, embeddings, metadata)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None
    ) -> List[Tuple[str, float, Dict]]:
        """语义搜索"""
        query_embedding = await self.embedding_model.encode(query)

        results = self.vector_store.search(
            query_vector=query_embedding,
            top_k=top_k,
            filters=filters
        )

        return results

    def delete(self, ids: List[str]) -> None:
        """删除"""
        self.vector_store.delete(ids)

    def save(self, path: str) -> None:
        """保存"""
        self.vector_store.save(path)

    def load(self, path: str) -> None:
        """加载"""
        self.vector_store.load(path)


# ============ 演示 ============

async def demo():
    """演示简化版语义记忆"""
    print("=== Simple Semantic Memory Demo ===\n")

    memory = SimpleSemanticMemory()

    # 添加记忆
    memories = [
        ("mem_1", "I love Python programming", {"type": "preference"}),
        ("mem_2", "I am working on machine learning", {"type": "context"}),
        ("mem_3", "PyTorch is my favorite framework", {"type": "preference"}),
        ("mem_4", "I am building a chatbot", {"type": "project"}),
    ]

    print("Adding memories...")
    for id_, content, meta in memories:
        await memory.add(id_, content, meta)
    print(f"Added {len(memories)} memories\n")

    # 搜索
    queries = [
        "What programming language do you like?",
        "What are you working on?",
        "Which ML framework do you prefer?",
    ]

    for query in queries:
        print(f"Query: {query}")
        results = await memory.search(query, top_k=2)

        for id_, score, meta in results:
            print(f"  [{id_}] (score: {score:.3f}) {meta['content']}")
        print()

    # 保存和加载
    print("Saving...")
    memory.save("./simple_vector_store")

    print("Loading...")
    memory2 = SimpleSemanticMemory()
    memory2.load("./simple_vector_store")

    print("Testing loaded memory...")
    results = await memory2.search("Python", top_k=1)
    for id_, score, meta in results:
        print(f"  [{id_}] (score: {score:.3f}) {meta['content']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
