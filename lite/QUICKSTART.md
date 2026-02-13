# Prime Lite v2 — Quick Start Guide

## 🚀 Installation

### Step 1: Initialize Prime
```bash
cd /path/to/prime/lite
python3 prime-lite-v2.py init
```

Creates:
- `~/.config/prime/prime.json` - Self-aware config
- `~/.config/prime/.env` - For API keys
- `~/.cache/prime/` - For caching

### Step 2: Configure API Keys (Optional)

Edit `~/.config/prime/.env`:
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Gemini
GEMINI_API_KEY=AQ....

# DeepSeek
DEEPSEEK_API_KEY=sk-...

# Kimi
KIMI_API_KEY=sk-...
```

**No API keys?** That's fine! Prime will use local Ollama instead.

### Step 3: Verify Setup

```bash
python3 prime-lite-v2.py status
```

You should see:
- ✓ Prime v2.0 initialized
- ✓ Hostname and environment info
- ✓ API status (which are available)
- ✓ Local Ollama running/offline

---

## 📝 Common Commands

### Who are you?
```bash
prime whoami
```
Responses:
- **Hostname**: Where Prime is running
- **Environment**: Local, VPS, Docker, etc.
- **APIs**: Which ones are configured & working
- **Features**: What Prime can do

### Check status
```bash
prime status
```
Shows:
- Self-awareness info
- Internet connectivity
- Available providers
- API key status

### Find projects
```bash
prime scan
```
Shows:
- All projects in workspace (recursive, 10 levels deep)
- Project type (Git, Node.js, Python, etc.)
- Git branch (if applicable)

### Build file index
```bash
prime index
```
Creates cache for fast file search.
Run once after adding new files.

### Ask a question
```bash
# Using installed prime command
prime "What is main.py about?"

# Or directly
python3 prime-lite-v2.py "Explain this code"

# Interactive mode
python3 prime-lite-v2.py
# Type your questions, press Ctrl+C to exit
```

---

## 💡 Smart Routing

Prime automatically chooses the best API:

### Query: "What is main.py?"
→ **Decision**: `simple`
→ **Provider**: `local` (Ollama)
→ **Speed**: Instant (uses cache)

### Query: "Write a function to parse CSV"
→ **Decision**: `code`
→ **Provider**: `anthropic` (best for code)
→ **Speed**: 2-3 seconds

### Query: "How should I structure this app?"
→ **Decision**: `arch`
→ **Providers**: `[anthropic, gemini]` (ensemble)
→ **Speed**: 5-10 seconds

### Query: "Explain the security implications"
→ **Decision**: `critical`
→ **Provider**: `anthropic` (best model)
→ **Speed**: 3-5 seconds

---

## 🔄 Resilience Features

### Feature 1: Automatic Fallback
```
Internet down?
→ Automatically use local Ollama
→ No errors, just works!
```

### Feature 2: Retry Logic
```
API timeout?
→ Retry after 1 second
→ Still fails? Retry after 2 seconds
→ Still fails? Retry after 4 seconds
→ All failed? Fall back to Ollama
```

### Feature 3: Result Caching
```
Asked same question before?
→ Instant response (< 100ms)
→ No API call, cached result
→ Cache expires after 1 hour
```

### Feature 4: Internet Check
```
Query to API?
→ Check internet first
→ Not connected? Use Ollama instead
→ Connected? Try API with retries
```

---

## 📂 File Locations

### Configuration
```
~/.config/prime/
├── prime.json        ← Self-aware config (auto-created)
└── .env              ← API keys (create manually)
```

### Cache
```
~/.cache/prime/
├── api_cache.json    ← Cached API results
└── file_index.json   ← File name index for fast search
```

### Prime Code
```
/path/to/prime/lite/
├── prime-lite-v2.py  ← Main program
├── resilience.py     ← API resilience
├── scanner.py        ← Project & file scanning
├── selfaware.py      ← Self-awareness
└── QUICKSTART.md     ← This file
```

---

## 🐛 Troubleshooting

### Problem: "Ollama error: Connection refused"

**Cause**: Ollama not running

**Solution**:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it:
ollama serve

# Or install if not present:
# https://ollama.ai/download
```

### Problem: "API error: Connection timeout"

**Cause**: Internet connection issue

**Solution**:
```bash
# Check internet
ping google.com

# If offline, Prime will automatically use Ollama
# Just wait and try again when online
```

### Problem: "File not found: main.py"

**Cause**: File isn't indexed yet

**Solution**:
```bash
# Rebuild file index
prime index

# Or use absolute path
prime "Read /home/user/project/main.py"
```

### Problem: "No API key set"

**Cause**: API key not configured

**Solution**:
```bash
# Edit config
nano ~/.config/prime/.env

# Add your key:
ANTHROPIC_API_KEY=sk-ant-...

# Save and test
prime status
```

---

## 🎯 Example Workflows

### Workflow 1: Analyze a project
```bash
# 1. Find all projects
prime scan

# 2. Check one out
cd /path/to/project

# 3. Ask about it
prime "What does this project do?"
prime "Explain the architecture"
prime "List the main components"
```

### Workflow 2: Code review
```bash
# 1. Navigate to code
cd /path/to/code

# 2. Get analysis
prime "Review this code for bugs"
prime "Any security issues?"
prime "How can this be optimized?"

# (Uses fuzzy file search - finds all relevant files)
```

### Workflow 3: Document generation
```bash
# 1. Index files
prime index

# 2. Generate docs
prime "Generate README.md for this project"
prime "Create API documentation"
prime "Write setup instructions"

# (All results cached for fast follow-ups)
```

---

## 📊 Performance Tips

### Tip 1: Use interactive mode
```bash
# Slower: Each query is separate
prime "What is main.py?"
prime "Explain the main function"
prime "How does it interact with other files?"

# Faster: Keep session alive
prime
>> What is main.py?
>> Explain the main function
>> How does it interact with other files?
# (Results are cached across questions)
```

### Tip 2: Build index for large projects
```bash
# Slow: First file search is slow
prime "Read utils/helpers/common.py"

# Fast: After indexing
prime index
prime "Read utils/helpers/common.py"  # Instant!
```

### Tip 3: Use specific file names
```bash
# Slow: Ambiguous
prime "Check config"  # Finds config.yaml, config.json, config.toml...

# Fast: Specific
prime "Check config.yaml"  # Finds exactly this file
```

---

## 🔐 Security Notes

1. **API Keys**: Stored in `~/.config/prime/.env` (readable by user only)
2. **Cache**: Results in `~/.cache/prime/` (includes API responses)
3. **Local Ollama**: No internet access needed
4. **File Permissions**: Auto-set to 0o600 (user only)

---

## 🌍 Environment Detection

Prime automatically detects where it's running:

```bash
$ prime whoami | grep Environment
Environment: Local/Development      # Your laptop
Environment: Docker                  # Inside container
Environment: Google Cloud (GCP)      # Google Cloud
Environment: AWS                     # Amazon AWS
Environment: VPS                     # Virtual Private Server
```

---

## 📞 Need Help?

1. **Check status**: `prime status`
2. **See config**: `prime whoami`
3. **View logs**: `cat ~/.config/prime/prime.json`
4. **Check cache**: `cat ~/.cache/prime/api_cache.json`

---

## 🎓 Concepts

### Smart Routing
Prime analyzes your query and picks the best API:
- Simple question → Local (instant)
- Code writing → Claude (best for code)
- Architecture → Ensemble (multiple views)
- Critical task → Best model (always correct)

### Graceful Degradation
If something fails, Prime finds a way:
- No internet → Use Ollama
- API timeout → Retry
- API error → Try next provider
- All fail → Fall back to Ollama

### Intelligent Caching
Prime remembers previous answers:
- Same question twice → Instant response
- Similar questions → Uses cached context
- Cache expires → Auto-refresh

### Recursive Scanning
Prime finds all your projects:
- Not just /workspace/project/
- Also /workspace/monorepo/packages/lib/
- Also /workspace/backend/v1/services/
- Up to 10 levels deep

### Fuzzy Finding
Prime finds the file you meant:
- "Read config" → Finds config.yaml
- "Check main" → Finds main.py, main.ts, main.go
- "test" → Finds test.py, tests/unit.py, test_data/

---

## 🚀 What's Next?

After getting comfortable with Prime:

1. **Add to PATH**: `ln -s ~/.local/bin/prime /path/to/prime-lite.py`
2. **Create alias**: `alias prime='python3 ~/.local/bin/prime'`
3. **Systemd service**: Run as background daemon (planned)
4. **Web UI**: Browser interface (planned)

---

**Happy coding!** 🎉

For more details, see `PRIME_CRITICAL_FIXES.md`
