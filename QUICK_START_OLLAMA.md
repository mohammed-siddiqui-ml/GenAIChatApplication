# Quick Start with Ollama (No OpenAI API Key Required!)

## 🚀 3-Step Setup

### Step 1: Configure
```bash
# Copy environment file
cp .env.example .env

# Edit .env and set:
LLM_PROVIDER=ollama
```

### Step 2: Start Services
```bash
# Start all services (includes Ollama)
docker-compose up -d

# Wait for services to be healthy (~1-2 minutes)
docker-compose ps
```

### Step 3: Download Models
```bash
# Run the automated setup script
./scripts/setup-ollama.sh

# Or download manually:
docker exec -it knowledge_ollama ollama pull llama2
docker exec -it knowledge_ollama ollama pull nomic-embed-text
```

## ✅ You're Done!

Access the application at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## 📝 Common Commands

### Check Installed Models
```bash
docker exec knowledge_ollama ollama list
```

### Test Chat Model
```bash
docker exec -it knowledge_ollama ollama run llama2 "Hello, how are you?"
```

### Download Different Model
```bash
# Smaller, faster model
docker exec -it knowledge_ollama ollama pull phi

# Update .env
LLM_PROVIDER=ollama
OLLAMA_CHAT_MODEL=phi

# Restart backend
docker-compose restart backend celery_worker
```

### Check Logs
```bash
# Ollama logs
docker logs knowledge_ollama

# Backend logs
docker logs knowledge_backend
```

### Restart Services
```bash
# Restart all
docker-compose restart

# Restart specific service
docker-compose restart ollama
docker-compose restart backend
```

## 🔧 CPU vs GPU

### Using CPU (Default)
```bash
# Use the CPU-only compose file
docker-compose -f docker-compose.yml -f docker-compose.ollama-cpu.yml up -d
```

### Using GPU (Faster)
```bash
# Default docker-compose.yml includes GPU support
docker-compose up -d
```

## 🎯 Model Selection Guide

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| `phi` | 1.6GB | ⚡⚡⚡ | ⭐⭐ | Testing, low resources |
| `llama2` | 4GB | ⚡⚡ | ⭐⭐⭐ | Production, balanced |
| `mistral` | 4GB | ⚡⚡ | ⭐⭐⭐ | Production, efficient |
| `llama3` | 4.7GB | ⚡ | ⭐⭐⭐⭐ | Best quality |

**Embedding Model**: `nomic-embed-text` (recommended for all cases)

## 🔄 Switch to OpenAI Later

Want to use OpenAI instead?

```bash
# Update .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here

# Restart
docker-compose restart backend celery_worker
```

## ❓ Troubleshooting

### Models not working?
```bash
# Check if models are downloaded
docker exec knowledge_ollama ollama list

# Download missing models
./scripts/setup-ollama.sh
```

### Slow responses?
```bash
# Use smaller model
docker exec -it knowledge_ollama ollama pull phi

# Update OLLAMA_CHAT_MODEL=phi in .env
# Restart: docker-compose restart backend
```

### Out of memory?
```bash
# Increase Docker memory (Docker Desktop → Settings → Resources)
# Or use smaller model (phi instead of llama2)
```

### Container won't start?
```bash
# Check logs
docker logs knowledge_ollama

# Remove GPU requirement if no GPU
docker-compose -f docker-compose.yml -f docker-compose.ollama-cpu.yml up -d
```

## 📚 Learn More

- [Full Setup Guide](OLLAMA_SETUP.md)
- [Integration Details](INTEGRATION_SUMMARY.md)
- [Available Models](https://ollama.com/library)
- [Ollama Documentation](https://github.com/ollama/ollama)

## 💡 Tips

1. **First time?** Use `phi` model for quick testing, switch to `llama2` for production
2. **Low on disk space?** Each model takes 2-5GB, delete unused ones with `ollama rm <model>`
3. **Want best quality?** Download `llama3` (but needs more RAM/disk)
4. **Multiple projects?** Models are shared across containers using the same volume

---

**Need help?** Check the logs: `docker logs knowledge_ollama` or `docker logs knowledge_backend`
