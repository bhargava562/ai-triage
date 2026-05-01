# QUICKSTART - Run the Agent in 5 Minutes

## Prerequisites
- Python 3.8+
- GROQ API key (get free key from https://console.groq.com/)

## Step 1: Set Your API Key (1 minute)

Edit the `.env` file in the repo root:
```bash
# Edit: ../.env
GROQ_API_KEY=gsk-your-actual-key-here
```

Get your key from: https://console.groq.com/

## Step 2: Run Setup (2 minutes)

From the `code/` directory:

**Windows:**
```bash
cd code
python setup.py
```

**macOS/Linux:**
```bash
cd code
python setup.py
```

This will:
- Create a virtual environment (`venv/`)
- Install all dependencies
- Validate your setup
- Print next steps

## Step 3: Validate Setup (30 seconds)

**Windows:**
```bash
run.bat --dry-run
```

**macOS/Linux:**
```bash
./run.sh --dry-run
```

Expected output:
```
Environment Validation Failed:
[!] GROQ_API_KEY is a placeholder
    Edit ../.env and add your actual API key
```

After you add your API key:
```
Environment validated
Dry run complete - environment is valid.
```

## Step 4: Test on Sample Tickets (1 minute)

**Windows:**
```bash
run.bat --sample
```

**macOS/Linux:**
```bash
./run.sh --sample
```

This processes 10 sample tickets. Uses ~$0.003 in API cost.

## Step 5: Process All Tickets (2-3 minutes)

**Windows:**
```bash
run.bat
```

**macOS/Linux:**
```bash
./run.sh
```

Output is written to: `../support_tickets/output.csv`

View results:
```bash
cat ../support_tickets/output.csv
```

## Directory Structure

```
hackerrank-orchestrate-may26/
├── code/                      (RUN FROM HERE)
│   ├── venv/                  (virtual environment - auto created)
│   ├── config.py              (settings)
│   ├── agent.py               (6-gate pipeline)
│   ├── main.py                (CLI entry point)
│   ├── setup.py               (one-command setup)
│   ├── run.bat                (Windows launcher)
│   ├── run.sh                 (Unix launcher)
│   ├── requirements.txt        (dependencies)
│   └── README.md              (detailed docs)
├── .env                       (API KEY - edit this!)
├── .env.example               (template)
├── data/                      (documentation - DO NOT MODIFY)
└── support_tickets/           (input/output - DO NOT MODIFY)
    ├── support_tickets.csv    (input)
    ├── sample_support_tickets.csv
    └── output.csv             (output - auto created)
```

## Quick Reference

| What | Windows | Unix |
|------|---------|------|
| Setup | `python setup.py` | `python setup.py` |
| Validate | `run.bat --dry-run` | `./run.sh --dry-run` |
| Test | `run.bat --sample` | `./run.sh --sample` |
| Full Run | `run.bat` | `./run.sh` |
| View Output | `type ..\support_tickets\output.csv` | `cat ../support_tickets/output.csv` |

## What Happens

1. **Agent loads documentation** (500+ markdown files)
2. **For each ticket:**
   - Gate 1: Filter trivial tickets
   - Gate 2: Check for dangerous content
   - Gate 3: Determine company (Visa/HackerRank/Claude)
   - Gate 4: Find relevant documentation
   - Gate 5: Generate response using GROQ LLM
   - Gate 6: Verify response is grounded
3. **Output CSV** with responses, confidence scores, justifications

## Output CSV Columns

| Column | Example |
|--------|---------|
| `issue` | Original ticket issue text |
| `subject` | Original ticket subject |
| `company` | Visa / HackerRank / Claude |
| `response` | Agent's answer or escalation notice |
| `product_area` | account_management, fraud, technical_support, etc. |
| `status` | replied or escalated |
| `request_type` | product_issue, feature_request, bug, invalid |
| `justification` | Why the agent made this decision |

## Troubleshooting

### "GROQ_API_KEY not set"
- Edit `../.env` and add your actual API key
- Make sure there's no `gsk-your-key-here` placeholder

### "venv command not found" (macOS/Linux)
```bash
chmod +x run.sh
./run.sh --dry-run
```

### "data/ directory not found"
- Make sure you're running from the `code/` directory
- `pwd` should show `.../hackerrank-orchestrate-may26/code`

### "ModuleNotFoundError"
```bash
python setup.py
```

## API Cost

**GROQ Pricing:**
- Input: $0.59 per 1M tokens
- Output: $0.79 per 1M tokens

**Typical Run (30 tickets):**
- API calls: ~21-25
- Cost: ~$0.02
- Time: 60-90 seconds

## Performance

| Category | Time |
|----------|------|
| Trivial/escalated (no LLM) | < 100ms |
| Normal (with LLM) | 2-3 seconds |
| Full batch (30 tickets) | 60-90 seconds |

## Next Steps

1. Get GROQ API key: https://console.groq.com/
2. Edit `../.env` with your key
3. Run `python setup.py`
4. Run `run.bat --sample` (Windows) or `./run.sh --sample` (Unix)
5. View results in `../support_tickets/output.csv`
6. Submit to HackerRank platform

Done! The agent is ready to triage support tickets. 🚀
