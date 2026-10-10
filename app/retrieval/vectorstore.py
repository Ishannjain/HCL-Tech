from functools import lru_cache
from pathlib import Path
import os
from app.config import get_settings

@lru_cache
def embedding_model():
    cache=Path(os.getenv('HF_HOME',str(get_settings().runtime_dir/'huggingface')))/'hub'
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(get_settings().embedding_model,cache_folder=str(cache))

@lru_cache
def collection():
    import chromadb
    from chromadb.config import Settings
    path = get_settings().runtime_dir / 'chroma'
    client = chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection('retail_policies',metadata={'hnsw:space':'cosine'})

def index_chunks(ids, chunks, doc_id):
    if get_settings().retrieval_backend != 'chroma':
        return
    texts = [c['text'] for c in chunks]
    embeddings = embedding_model().encode(texts,normalize_embeddings=True).tolist()
    collection().upsert(ids=ids,documents=texts,embeddings=embeddings,
        metadatas=[{'doc_id':doc_id,'section':c['section'],'page':c['page']} for c in chunks])

def delete_ids(ids):
    if ids and get_settings().retrieval_backend == 'chroma':
        collection().delete(ids=ids)

def search_vector(question, allowed_docs, top_k):
    if not allowed_docs:
        return []
    vector = embedding_model().encode([question],normalize_embeddings=True).tolist()
    output = collection().query(query_embeddings=vector, n_results=min(top_k, max(1,collection().count())),
                                where={'doc_id':{'$in':allowed_docs}})
    return [{'chunk_id':cid,'score':1-distance} for cid,distance in zip(output['ids'][0],output['distances'][0])]
