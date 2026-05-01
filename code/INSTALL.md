# Installation & Execution Guide

## Complete Setup in 3 Steps

### Step 1: Configure API Key

Edit the `.env` file in the repository root:

```bash
# File: ../.env (in repo root, NOT in code/)

GROQ_API_KEY=gsk-your-actual-api-key-here
```

Get a free GROQ API key from: https://console.groq.com/

### Step 2: Run Setup Script

From the `code/` directory:

```bash
cd code
python setup.py
```

This script will:
- Create a virtual environment (`venv/`)
- Install all dependencies (groq, rank-bm25, rich, python-dotenv, langdetect, tiktoken)
- Validate your directory structure
- Verify Python modules load correctly
- Print next steps

**Expected output:**
```
[+] Python version: 3.14.x
[+] Virtual environment already exists
[*] Installing dependencies...
    [+] groq>=0.4.0
    [+] rank-bm25>=0.2.2
    ...
[*] Testing code imports...
    [+] All modules import successfully

SETUP COMPLETE - OK
```

### Step 3: Run the Agent

From the `code/` directory, use one of these commands:

#### Validate Setup (no API calls, no data processing)
```bash
# Windows
run.bat --dry-run

# macOS/Linux
./run.sh --dry-run
```

Expected output:
```
+ Environment validated
+ Dry run complete -- environment is valid.
```

#### Test on Sample Tickets (10 tickets, ~$0.003 cost)
```bash
# Windows
run.bat --sample

# macOS/Linux
./run.sh --sample
```

#### Process All Tickets (29 tickets, ~$0.02 cost)
```bash
# Windows
run.bat

# macOS/Linux
./run.sh
```

#### View Results
```bash
# Windows
type ..\support_tickets\output.csv

# macOS/Linux
cat ../support_tickets/output.csv
```

---

## Directory Structure

```
hackerrank-orchestrate-may26/
│
├── .env                               [EDIT THIS - add API key]
├── .env.example                       [Template]
│
├── code/                              [WORK FROM HERE]
│   ├── venv/                          [Auto-created by setup.py]
│   │
│   ├── setup.py                       [One-command setup]
│   ├── run.bat                        [Windows launcher]
│   ├── run.sh                         [Unix launcher]
│   │
│   ├── main.py                        [CLI entry point]
│   ├── agent.py                       [6-gate pipeline]
│   ├── config.py                      [Settings & constants]
│   ├── safety.py                      [Gate 2: Safety]
│   ├── router.py                      [Gate 3: Routing]
│   ├── retriever.py                   [Gate 4: Retrieval]
│   ├── generator.py                   [Gate 5: Generation]
│   ├── auditor.py                     [Gate 6: Auditing]
│   ├── formatter.py                   [Terminal UI]
│   │
│   ├── requirements.txt
│   ├── README.md                      [Detailed docs]
│   ├── QUICKSTART.md                  [Quick reference]
│   └── setup.py                       [Setup automation]
│
├── data/                              [DO NOT MODIFY]
│   ├── claude/
│   ├── hackerrank/
│   └── visa/
│
└── support_tickets/                   [DO NOT MODIFY]
    ├── support_tickets.csv            [Input - 29 tickets]
    ├── sample_support_tickets.csv     [Input - 10 sample tickets]
    └── output.csv                     [Output - auto-created]
```

---

## Files You Can Modify

- ✏️ `.env` — Add your GROQ API key
- ✏️ Files in `code/` — Can be edited for customization

## Files You CANNOT Modify

- 🔒 `data/` — Documentation corpus (read-only)
- 🔒 `support_tickets/input CSV files` — Ticket data (read-only)
- 🔒 Python code in `code/` — Don't edit unless you know what you're doing

---

## Quick Reference Commands

| Task | Windows | Unix |
|------|---------|------|
| Setup | `python setup.py` | `python setup.py` |
| Validate | `run.bat --dry-run` | `./run.sh --dry-run` |
| Test | `run.bat --sample` | `./run.sh --sample` |
| Full Run | `run.bat` | `./run.sh` |
| View Output | `type ..\support_tickets\output.csv` | `cat ../support_tickets/output.csv` |
| Check API Key | `type ..\env` | `cat ../.env` |

---

## What Each Command Does

### `python setup.py`
- ✓ Creates virtual environment
- ✓ Installs all dependencies
- ✓ Validates setup
- ✓ Tests imports
- 📌 Run this once per system setup

### `run.bat --dry-run` / `./run.sh --dry-run`
- ✓ Validates API key is set
- ✓ Checks data/ and support_tickets/ directories
- ✗ Does NOT call the LLM
- ✗ Does NOT process any tickets
- 💰 Cost: $0.00
- ⏱️ Time: < 1 second

### `run.bat --sample` / `./run.sh --sample`
- ✓ Processes 10 sample tickets
- ✓ Calls GROQ LLM API
- ✓ Writes to output.csv
- 💰 Cost: ~$0.003
- ⏱️ Time: ~15-20 seconds

### `run.bat` / `./run.sh`
- ✓ Processes all 29 tickets
- ✓ Calls GROQ LLM API for each
- ✓ Writes to output.csv
- 💰 Cost: ~$0.02
- ⏱️ Time: ~60-90 seconds

---

## Troubleshooting

### "GROQ_API_KEY not set" or "placeholder"

**Solution:**
```bash
# Edit ../.env (in repo root)
GROQ_API_KEY=gsk-your-actual-key-from-groq-console
```

Get your key: https://console.groq.com/keys

### "venv not found" / "No module named 'venv'"

**Solution:**
```bash
python setup.py
```

This will create and configure the venv automatically.

### "data/ directory not found"

**Solution:**
Make sure you're running from the `code/` directory:
```bash
cd code
pwd  # Should show: .../hackerrank-orchestrate-may26/code
run.bat  # Windows or
./run.sh  # Unix
```

### "ModuleNotFoundError: No module named 'groq'"

**Solution:**
```bash
python setup.py
```

This will reinstall all dependencies.

### "Permission denied" on `run.sh` (macOS/Linux)

**Solution:**
```bash
chmod +x run.sh
./run.sh --dry-run
```

### Output CSV is empty or has errors

**Solution:**
1. Check your GROQ API key is valid
2. Check the `.env` file exists and has your key
3. Run `--dry-run` first to validate setup
4. Check `../support_tickets/support_tickets.csv` exists

---

## File Descriptions

| File | Purpose |
|------|---------|
| `setup.py` | Automated setup script (creates venv, installs deps) |
| `run.bat` | Windows launcher (activates venv, runs main.py) |
| `run.sh` | Unix launcher (activates venv, runs main.py) |
| `main.py` | CLI entry point (argument parsing, file I/O) |
| `agent.py` | Core 6-gate pipeline orchestrator |
| `config.py` | All constants, thresholds, DNA maps (settings only) |
| `safety.py` | Gate 2: Radioactive content & injection detection |
| `router.py` | Gate 3: Brand fingerprinting (deterministic routing) |
| `retriever.py` | Gate 4: BM25 corpus loader & retrieval |
| `generator.py` | Gate 5: LLM response generation (GROQ API call) |
| `auditor.py` | Gate 6: Two-phase fidelity verification |
| `formatter.py` | Rich terminal dashboard (UI) |
| `requirements.txt` | Python dependencies |
| `QUICKSTART.md` | 5-minute quick start |
| `README.md` | Detailed architecture & design docs |

---

## Performance Expectations

### Speed
- Trivial/escalated (no LLM): < 100ms
- Normal (with LLM): 2-3 seconds per ticket
- Batch of 29 tickets: 60-90 seconds

### Cost (GROQ Llama 3.3 70B)
- Per API call: ~$0.0008
- Per 29-ticket batch: ~$0.02
- 10-ticket sample: ~$0.003

### Output
- CSV with columns: issue, subject, company, response, product_area, status, request_type, justification
- Automatically written to: `../support_tickets/output.csv`

---

## Submitting Results

After running the agent:

1. View output: `cat ../support_tickets/output.csv`
2. Submit to HackerRank platform per challenge instructions
3. Results ready: May 2, 2026, 11:00 IST deadline

---

## Support

For detailed information, see:
- `code/QUICKSTART.md` — 5-minute quick reference
- `code/README.md` — Complete architecture guide
- `code/setup.py` — Automated setup with validation

**Ready to start?** Run: `python setup.py`
