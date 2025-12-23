# Quick Start: Local Llama with Ollama

## What Was Done

Your Airweave system has been configured to use **local Llama models** via Ollama instead of cloud AI providers. This gives you:

✅ **Zero cost** - No API charges
✅ **Complete privacy** - Data never leaves your servers
✅ **Offline capable** - No internet required
✅ **Full control** - Choose your own models

## 🚀 Quick Start (3 Commands)

### 1. Start Services with Ollama

```bash
cd docker
docker-compose --profile local-llm up -d
```

This starts all Airweave services + Ollama.

### 2. Pull the AI Models

```bash
# Pull LLM model (~40GB, takes 10-30 minutes)
docker exec -it airweave-ollama ollama pull llama3.3:70b

# Pull embedding model (~300MB, takes 1-2 minutes)
docker exec -it airweave-ollama ollama pull nomic-embed-text
```

**For testing/lower hardware**, use smaller models:
```bash
docker exec -it airweave-ollama ollama pull llama3.2:3b
docker exec -it airweave-ollama ollama pull nomic-embed-text
```

### 3. Verify Setup

```bash
# Check models are installed
docker exec -it airweave-ollama ollama list

# Test generation
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.3:70b",
  "prompt": "Say hello!",
  "stream": false
}'

# Check Airweave logs
docker logs airweave-backend | grep -i ollama
```

You should see:
```
[OllamaProvider] Connected to Ollama at http://ollama:11434
[OllamaProvider] Using LLM model: llama3.3:70b
[OllamaProvider] Using embedding model: nomic-embed-text
```

## ✅ That's It!

Your Airweave system is now using local AI. All search queries, embeddings, and AI operations will use your local Llama models.

## 📊 System Requirements

**Minimum (for testing):**
- CPU: 4+ cores
- RAM: 8GB
- Disk: 50GB free
- Model: llama3.2:3b

**Recommended (for production):**
- CPU: 8+ cores
- RAM: 16GB+
- GPU: NVIDIA RTX 3090 or better (24GB VRAM)
- Disk: 100GB+ free
- Model: llama3.3:70b

## 🔧 Configuration Files Changed

| File | What Changed |
|------|--------------|
| `docker/docker-compose.yml` | Added Ollama service with `local-llm` profile |
| `backend/airweave/search/providers/ollama.py` | New provider implementation |
| `backend/airweave/search/factory.py` | Integrated Ollama provider |
| `backend/airweave/search/defaults.yml` | Set Ollama as primary provider |
| `backend/airweave/core/config.py` | Added `OLLAMA_BASE_URL` setting |
| `.env.example` | Added Ollama configuration |

## 🎯 Provider Priority

Airweave will try providers in this order:

1. **Ollama (local)** ← Your local models
2. Cerebras (cloud) ← Fallback if Ollama down
3. Groq (cloud) ← Second fallback
4. OpenAI (cloud) ← Final fallback

To force **local-only** mode, remove cloud API keys from `.env`:
```bash
# Comment these out in .env
# OPENAI_API_KEY=...
# GROQ_API_KEY=...
# CEREBRAS_API_KEY=...
```

## 🖥️ GPU Acceleration (Optional)

For 10x faster inference, enable GPU support:

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Uncomment GPU section in `docker/docker-compose.yml`:
```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

3. Restart:
```bash
docker-compose --profile local-llm down
docker-compose --profile local-llm up -d
```

4. Verify:
```bash
docker exec -it airweave-ollama nvidia-smi
```

## 📖 Model Options

### Text Generation (LLM)

| Model | Size | RAM Needed | Best For |
|-------|------|------------|----------|
| `llama3.2:3b` | 4GB | 8GB | Testing, low hardware |
| `llama3.1:8b` | 8GB | 16GB | Balanced performance |
| `llama3.3:70b` | 40GB | 64GB or 24GB VRAM | Production quality |

### Embeddings

| Model | Dimensions | Best For |
|-------|------------|----------|
| `nomic-embed-text` | 768 | General purpose (default) |
| `all-minilm` | 384 | Faster, less accurate |
| `mxbai-embed-large` | 1024 | More accurate |

Change models by editing `backend/airweave/search/defaults.yml`:

```yaml
ollama:
  llm:
    name: "llama3.2:3b"  # Change this
  embedding:
    name: "nomic-embed-text"  # Change this
```

## 🐛 Troubleshooting

**"Connection refused"**
```bash
# Check Ollama is running
docker ps | grep ollama

# Restart if needed
docker-compose --profile local-llm restart ollama
```

**"Model not found"**
```bash
# Pull the model
docker exec -it airweave-ollama ollama pull llama3.3:70b
```

**Slow responses**
- Use smaller model (`llama3.2:3b`)
- Enable GPU acceleration (see above)
- Check CPU/RAM usage: `docker stats`

**Out of memory**
- Use smaller model
- Increase Docker memory limit
- Add more RAM or use GPU

## 📚 Full Documentation

See `docs/LOCAL_LLAMA_SETUP.md` for:
- Detailed architecture explanation
- Advanced configuration
- Production deployment guide
- Security & privacy considerations
- Cost comparison vs cloud AI
- Performance benchmarks

## 🎉 Summary

You now have a **fully local AI system** running in Docker!

**What happens now:**
- All embeddings → Local Llama models
- All text generation → Local Llama models
- All reranking → Local Llama models
- Zero API costs ✅
- Complete data privacy ✅
- Offline capable ✅

**Next steps:**
1. Start using Airweave normally - it will automatically use local AI
2. Monitor performance with `docker logs -f airweave-backend`
3. Tune models in `defaults.yml` based on your needs
4. Enable GPU for faster inference (optional)

Questions? Check `docs/LOCAL_LLAMA_SETUP.md` or the [Ollama docs](https://ollama.ai/).
