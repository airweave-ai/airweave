evals: representative queries with annotated relevant documents

query rewriting: https://docs.vespa.ai/en/linguistics/query-rewriting.html#
retrieval fusion: https://blog.vespa.ai/improving-zero-shot-ranking-with-vespa/
ColBERT embedder: https://blog.vespa.ai/announcing-colbert-embedder-in-vespa/ (each query token to interact with all document tokens instead of pooling into one vector + same words at different positions get different encoding (SPLADE) + cross-encodes concat the two inputs into a single forward pass)
pre-trained language models for text ranking: https://blog.vespa.ai/pretrained-transformer-language-models-for-search-part-1/


Cross-encoder: 
take query and document together as one sequence and do single forward pass of the transformer model. Therefor query tokens can attend directly to document tokens. The repr of the doc DEPENDS on the query. So you can't pre-compute the embeddings. 

ColBERT: 
encode doc and query separately. Compute interactoin between all token vectors.

SPLADE: 
neural sparse embedder that forces most entries to zero (bm25 like but learned)

Matryoshka: 1 large vector where prefixes of the vector are themselves good embeddings
e.g. [1, 2, ..., 100] -> [1, 2, ..., 10] usable, [1, 2, ..., 30] better, etc
so you can simple cut parts off to speed things up

Phased Ranking:
- retrieval in content nodes using query API
- ranking in content or stateless nodes using rank-profile
    - first phase: evaluated on all hits
    - second phase: re-rank the top scoring hits
    - global phase: after contennt nodes have returned the top-scoring hits to the stateless container

Layered ranking: 
- chunk-level docs (what we have): each chunk is a doc
    - lack context
    - duplicate metadata
    - large doc sets
- multi-chunk docs: one doc with "chunks" field
    - large context window -> layered ranking solution
1. Use ranking function to score entire docs (e.g. aggregate over chunks)
2. For top-N docs, compute per chunk scores
self: but then chunking is done in Vespa

Understand RAG use case:

Indexing pipeline:
- runs when document is ingested
- expression: store current value of pipeline in sink
    - attribute: filtering, sorting, grouping, fast access, etc (IN-MEMORY, for direct lookup)
    - index: build inverted index (DISK-BACKED, for text search)
    - summary: store field in response payload (what to return e.g. top 3 chunks per doc)
example: field chunk_embeddings type tensor<int8>(chunk{}, x[96]) {
    indexing: input text | chunk fixed-length 1024 | embed | pack_bits | attribute | index
    attribute {
        distance-metric: hamming
    }
} -> text -> chunks -> embed (each chunk into float vector) -> convert to binary vector (calc distance with hamming) -> make elibible for index

summary feature: e.g. what chunks to be returned
- if query and doc embedding are same dimension and numeric type -> closeness
- otherwise have to unpack + calc cosine similarity yourself

index different textual content separately: title and text, if the added memory justifies the quality improvement

- metadata for filtering ranking, grouping
- signals for ranking

parent/child + document references: import fields without having to store them in each child. Also automatically updated in the child.

llms: possible to send query to vespa and output + query to openai in one request

query profile: named bundle of query parameters (e.g. rag, deep research)
- what query to run
- what summary profile to use, what rank profile
- here: embed query twice -> binary for retrieval and float for ranking
    float embedding is used in rank profile
    binary embedding (don't see it being used yet)

targetHist: candidate pool (higher is higher recall + more latency)
rerank-count: number of candidates to rerank
these parameters apply per node, so not total over all nodes

userInput(@query): weakAnd over the query terms against the default fieldset

rank() operator: only first argument is used for matching, rest is used for ranking
instead of where ... or ...: retrieve candidate set of union

Embedder choice:
trade-off: inference time + memory usage and quality
leaderboard: check retrieval, memory usage, vector dimensions and context length
BYO onnx model file + specify in services.xml -> vespa hosts and runs the model
types: dense, sparse, multi-vector (colbert), all (bge-m3 model)

binarization: float -> single bit -> pack 8 single bits in int8
(useful for match-phase)
otherwise you have to "page the vectors to disk"

recommendation:
- binarize vectors, hamming distance, attribute (in memory), with index
- higher precision ranking: float embedding, cosine distance, paged to disk (NO INDEX)
    no index:
        - keep tensor as in-memory attribute
        - build HNSW graph index over it
        self: why index when we are not looking for fast retrieval but are ranking a small subset
- still embed query with floats, and compute distance by unpacking the binarized vectors

weakAnd: fast OR with a budget

improve recalll:
    - better embedding model
    - increase targetHits
    - tune HSNW parameters
improve precision: text-level knobs
    near: query terms have to be close together in matching doc
    phrase: appear as exact phrase
    equiv: equivalance classes (llm, large language model, gpt)
    lunguistics
improve latency:
    - tune weakAnd parameters

First-phase ranking:
- computationally cheap since input is all retrieved docs
    e.g. learned linear combination of "text features + vector closeness + metadata"
- bm25 (no proximity), nativeRank, fieldMatch (too expensive)

learn the coefficients of our features
a * bm25(chunks) + b * avg_top_3_chunk_sim_scores()

    1. define rank-profile that will collect the match-features
    2. use VespaFeatureCollector to calc features for each (query, doc) pair
        - creates query with ranking profile "collect-training-data"
        - calls recall parameter so vespa is forced to return all relevant docs even if outside of top-K
    3. runs query and returns:
        score for each feature (e.g. bm25 score of title is ...)
        relevance (random number b/c second phase is random)
    4. keep all positives, sample some random negatives
    5. using the feature values (X) and the relevance_label (y) we can learn the coeffs
    6. keep unseen test set to eval the model on

random hits: subset of non-relevant docs for query, because all pairs aer too many