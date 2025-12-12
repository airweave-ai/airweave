# Local Llama AI Setup with Ollama

This guide explains how to configure Airweave to use local Llama models via Ollama instead of cloud AI providers (OpenAI, Groq, Cerebras).

## Overview

Airweave now supports running Llama models locally using [Ollama](https://ollama.ai/). This allows you to:

- **Run completely offline** - No internet required, no API keys needed
- **Zero cost** - No per-token charges for AI operations
- **Data privacy** - Your data never leaves your infrastructure
- **Full control** - Choose your models and parameters
- **Customization** - Fine-tune models for your specific use case

## Architecture

Ollama has been integrated as a first-class provider in Airweave's multi-provider architecture:

- **Text Generation**: Query expansion, answer generation, federated search
- **Embeddings**: Document and query embeddings for semantic search
- **Reranking**: Document relevance scoring
- **Structured Output**: JSON schema-based responses

Ollama is configured as the **primary provider** with automatic fallback to cloud providers if needed.

## Prerequisites

- Docker and Docker Compose installed
- At least 8GB RAM (16GB+ recommended for larger models)
- Storage space for models (4GB-40GB per model depending on size)

**Optional but Recommended:**
- NVIDIA GPU with Docker GPU support for faster inference
- 16GB+ VRAM for 70B parameter models

## Quick Start

### 1. Enable Local LLM Profile

The Ollama service is defined in `docker/docker-compose.yml` under the `local-llm` profile.

Start all services including Ollama:

```bash
cd docker
docker-compose --profile local-llm up -d
```

Or start only specific services:

```bash
# Start core services + Ollama
docker-compose --profile local-llm up -d postgres redis qdrant ollama backend
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# Local AI Configuration
OLLAMA_BASE_URL=http://localhost:11434

# Optional: Disable cloud providers to force local-only mode
# OPENAI_API_KEY=
# GROQ_API_KEY=
# CEREBRAS_API_KEY=
# COHERE_API_KEY=
```

**For Docker deployment**, the environment is automatically configured via `docker-compose.yml`:
- Backend service: `OLLAMA_BASE_URL=http://ollama:11434`
- Temporal worker: Same configuration as backend

### 3. Pull Required Models

After Ollama is running, pull the required models:

```bash
# Pull the LLM model (default: llama3.3:70b)
docker exec -it airweave-ollama ollama pull llama3.3:70b

# Pull the embedding model (default: nomic-embed-text)
docker exec -it airweave-ollama ollama pull nomic-embed-text
```

**Verify models are installed:**

```bash
docker exec -it airweave-ollama ollama list
```

Expected output:
```
NAME                    ID              SIZE    MODIFIED
llama3.3:70b           abc123...       40 GB   2 minutes ago
nomic-embed-text       def456...       274 MB  1 minute ago
```

### 4. Test the Setup

Check Ollama health:

```bash
curl http://localhost:11434/api/tags
```

Test text generation:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.3:70b",
  "prompt": "What is machine learning?",
  "stream": false
}'
```

Test embeddings:

```bash
curl http://localhost:11434/api/embeddings -d '{
  "model": "nomic-embed-text",
  "prompt": "Hello world"
}'
```

## Model Selection

### Default Models (configured in `backend/airweave/search/defaults.yml`)

```yaml
ollama:
  llm:
    name: "llama3.3:70b"          # Text generation model
    tokenizer: "cl100k_base"
    context_window: 128000
  embedding:
    name: "nomic-embed-text"      # Embedding model (768-dim)
    tokenizer: "cl100k_base"
    dimensions: 768
    max_tokens: 8192
  rerank:
    name: "llama3.3:70b"          # Reranking model
    tokenizer: "cl100k_base"
    context_window: 128000
```

### Alternative Models

You can use different models based on your requirements:

#### For Lower Hardware Requirements:

**Small LLMs (4-8GB VRAM):**
```bash
docker exec -it airweave-ollama ollama pull llama3.2:3b
```

Update `defaults.yml`:
```yaml
ollama:
  llm:
    name: "llama3.2:3b"
```

**Medium LLMs (8-16GB VRAM):**
```bash
docker exec -it airweave-ollama ollama pull llama3.1:8b
```

#### For Better Performance:

**Large LLMs (24GB+ VRAM):**
```bash
docker exec -it airweave-ollama ollama pull llama3.3:70b
docker exec -it airweave-ollama ollama pull llama3.1:405b  # Requires 200GB+ VRAM
```

#### Alternative Embedding Models:

```bash
# Smaller, faster (384-dim)
docker exec -it airweave-ollama ollama pull all-minilm

# Larger, more accurate (1024-dim) - requires updating dimensions in defaults.yml
docker exec -it airweave-ollama ollama pull mxbai-embed-large
```

**Available Models:** https://ollama.ai/library

## GPU Support

### Enable NVIDIA GPU Acceleration

Uncomment the GPU configuration in `docker/docker-compose.yml`:

```yaml
ollama:
  container_name: airweave-ollama
  image: ollama/ollama:latest
  profiles:
    - local-llm
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

**Prerequisites:**
1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
2. Verify GPU access: `docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi`

**Restart services:**

```bash
docker-compose --profile local-llm down
docker-compose --profile local-llm up -d
```

**Verify GPU is being used:**

```bash
docker exec -it airweave-ollama nvidia-smi
```

## Provider Priority & Fallback

Airweave uses a **provider preference system** with automatic fallback:

### Current Priority (configured in `defaults.yml`):

1. **Ollama** (local) - Tried first
2. **Cerebras** (cloud) - Fallback if Ollama unavailable
3. **Groq** (cloud) - Fallback if both above unavailable
4. **OpenAI** (cloud) - Final fallback

### Force Local-Only Mode

To ensure **only local models** are used (no cloud fallback):

**Option 1: Remove cloud API keys from `.env`:**
```bash
# Comment out or remove these lines
# OPENAI_API_KEY=sk-...
# GROQ_API_KEY=gsk_...
# CEREBRAS_API_KEY=csk_...
# COHERE_API_KEY=...
```

**Option 2: Modify `defaults.yml` to use only Ollama:**

```yaml
operation_preferences:
  query_expansion:
    order:
      - provider: ollama
        llm: llm

  embed_query:
    order:
      - provider: ollama
        embedding: embedding

  # ... same for all operations
```

## Monitoring & Troubleshooting

### Check Ollama Logs

```bash
docker logs -f airweave-ollama
```

### Check Backend Logs

```bash
docker logs -f airweave-backend
```

Look for provider initialization:
```
[OllamaProvider] Connected to Ollama at http://ollama:11434
[OllamaProvider] Using LLM model: llama3.3:70b
[OllamaProvider] Using embedding model: nomic-embed-text (768-dim)
```

### Common Issues

**Issue: "Failed to initialize Ollama client"**
- Verify Ollama service is running: `docker ps | grep ollama`
- Check Ollama health: `curl http://localhost:11434/api/tags`
- Ensure `OLLAMA_BASE_URL` is set correctly

**Issue: "Model not found"**
- Pull the required model: `docker exec -it airweave-ollama ollama pull llama3.3:70b`
- Verify models: `docker exec -it airweave-ollama ollama list`

**Issue: Slow inference**
- Enable GPU support (see GPU section above)
- Use smaller models (e.g., llama3.2:3b instead of llama3.3:70b)
- Increase Docker memory limits

**Issue: Out of memory**
- Use smaller models
- Reduce concurrent requests
- Increase system RAM or Docker memory limits

### Performance Metrics

**Expected Performance (CPU-only, 16GB RAM):**
- Llama 3.2 3B: ~5-10 tokens/sec
- Llama 3.1 8B: ~2-5 tokens/sec
- Llama 3.3 70B: Not recommended on CPU

**Expected Performance (NVIDIA RTX 3090, 24GB VRAM):**
- Llama 3.2 3B: ~100+ tokens/sec
- Llama 3.1 8B: ~50-80 tokens/sec
- Llama 3.3 70B: ~10-20 tokens/sec

## Advanced Configuration

### Custom Model Parameters

Create a custom Modelfile for fine-tuned inference:

```bash
docker exec -it airweave-ollama sh -c 'cat > /tmp/Modelfile << EOF
FROM llama3.3:70b

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_ctx 128000

SYSTEM You are a helpful AI assistant integrated into Airweave.
EOF'

docker exec -it airweave-ollama ollama create airweave-llama -f /tmp/Modelfile
```

Update `defaults.yml`:
```yaml
ollama:
  llm:
    name: "airweave-llama"
```

### Multiple Ollama Instances

Run multiple Ollama instances for different models:

```yaml
# docker-compose.yml
services:
  ollama-llm:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_llm_data:/root/.ollama

  ollama-embeddings:
    image: ollama/ollama:latest
    ports:
      - "11435:11434"
    volumes:
      - ollama_embedding_data:/root/.ollama
```

Configure different base URLs in your code or environment variables.

## Migration from Cloud to Local

### 1. Backup Existing Embeddings

If you're migrating from OpenAI embeddings (1536-dim) to Ollama (768-dim), you'll need to re-embed your documents.

### 2. Re-index Collections

After switching to Ollama embeddings:

```bash
# Via API or admin interface, trigger re-indexing for all collections
# This will re-embed documents using the new embedding model
```

### 3. Test Parity

Compare search quality between cloud and local models:
- Run the same queries on both setups
- Evaluate answer quality
- Measure response times

### 4. Gradual Migration

Use the fallback system during migration:
1. Keep cloud API keys active
2. Set Ollama as primary provider
3. Monitor error rates and fallback frequency
4. Remove cloud API keys once confident

## Cost Comparison

### Cloud AI Costs (estimated):

**OpenAI GPT-4o:**
- Input: $2.50 / 1M tokens
- Output: $10.00 / 1M tokens
- Embeddings: $0.13 / 1M tokens

**Example: 10M queries/month with RAG:**
- 10M queries × 500 input tokens = 5B tokens = $12,500
- 10M answers × 100 output tokens = 1B tokens = $10,000
- 10M embeddings × 1000 tokens = 10B tokens = $1,300
- **Total: ~$23,800/month**

### Local AI Costs:

**One-time setup:**
- Server: $2,000-5,000 (GPU workstation)
- Power: $50-150/month (24/7 operation)

**Amortized monthly cost:**
- Hardware (3-year depreciation): $55-140/month
- Power: $50-150/month
- **Total: ~$105-290/month**

**Breakeven: ~1-2 months for high-volume usage**

## Security & Privacy

### Benefits of Local Deployment:

✅ **Data never leaves your network** - Full GDPR/HIPAA compliance
✅ **No third-party access** - No OpenAI/Anthropic API calls
✅ **Audit trail** - Complete control over logs
✅ **Air-gapped deployment** - Can run fully offline
✅ **No rate limits** - Only limited by your hardware

### Considerations:

- Ensure Docker volumes are encrypted at rest
- Secure Ollama API endpoint (not exposed publicly by default)
- Implement proper access controls for model management
- Monitor for model updates and security patches

## Production Deployment

### Recommended Setup:

1. **Dedicated GPU server** for Ollama
2. **Load balancing** multiple Ollama instances
3. **Monitoring** with Prometheus + Grafana
4. **Autoscaling** based on request queue depth
5. **Model caching** with Redis for frequently used responses

### High Availability:

```yaml
# docker-compose.yml
services:
  ollama-1:
    image: ollama/ollama:latest
    # ... GPU config

  ollama-2:
    image: ollama/ollama:latest
    # ... GPU config

  ollama-lb:
    image: nginx:alpine
    volumes:
      - ./nginx-ollama.conf:/etc/nginx/nginx.conf
```

Configure backend to use load balancer:
```bash
OLLAMA_BASE_URL=http://ollama-lb:11434
```

## Resources

- **Ollama Documentation**: https://ollama.ai/
- **Llama Models**: https://ollama.ai/library/llama3.3
- **Embedding Models**: https://ollama.ai/library/nomic-embed-text
- **GPU Setup**: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
- **Model Fine-tuning**: https://github.com/ollama/ollama/blob/main/docs/modelfile.md

## Support

For issues or questions:
1. Check logs: `docker logs airweave-ollama` and `docker logs airweave-backend`
2. Verify configuration in `defaults.yml` and `.env`
3. Test Ollama directly: `curl http://localhost:11434/api/tags`
4. Open an issue on GitHub with logs and configuration details

## Summary

You've now configured Airweave to use local Llama models via Ollama! This gives you:

✅ **Privacy** - Data stays local
✅ **Cost savings** - No per-token charges
✅ **Control** - Choose and tune your models
✅ **Reliability** - No dependency on external APIs
✅ **Flexibility** - Automatic fallback to cloud if needed

Start with `llama3.2:3b` for testing, then scale up to `llama3.3:70b` or larger models as needed.
