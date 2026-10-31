# Automation Advisor - Quick Start Guide

## 🎯 What is this?

Interactive decision framework that helps you decide whether to automate a task using **data**, not gut feeling.

Based on the [[Automation Decision Matrix]] with visual outputs and Obsidian integration.

## 🚀 Quick Start

### Option 1: See Examples First (Recommended)

```bash
cd ~/.claude/skills/automation-advisor
python3 test_demo.py
```

Shows 4 real examples with visualizations (invoice generation, reports, social media, onboarding).

### Option 2: Run Interactive Questionnaire

```bash
cd ~/.claude/skills/automation-advisor
python3 server.py --mode console
```

Answer 8 questions → Get decision → Get markdown report in your vault.

### Option 3: Web Server (Voice-Enabled) 🎤

```bash
cd ~/.claude/skills/automation-advisor
./start_server.sh
```

Then open: [url-1]

**Features**:
- Modern web UI with dark theme
- Voice input (click 🎤 to speak your answer)
- Voice output (questions read aloud)
- Real-time progress tracking
- Works on phone/tablet

### Option 4: Use via Claude Code (Coming Soon)

```bash
/automation-advisor
```

## 📊 What You Get

### 1. Clear Decision
- ✅ **AUTOMATE NOW** (score > 40)
- 🤔 **AUTOMATE IF EASY** (score 20-40, < 4 hours to build)
- ❌ **STAY MANUAL** (score < 20)

### 2. Visual Analysis
```
╔══════════════════════════════════════════════╗
║      AUTOMATION SCORE BREAKDOWN              ║
╠══════════════════════════════════════════════╣
║  Frequency    [3/5] ████████████             ║
║  Time         [5/5] ████████████████████     ║
║  Error Cost   [5/5] ████████████████████     ║
║  Longevity    [3/5] ████████████             ║
║  Total Score: 225                            ║
╚══════════════════════════════════════════════╝
```

### 3. Break-Even Timeline
Shows when automation pays for itself (build time vs. time saved).

### 4. Risk Assessment
Identifies 7 potential red flags (high-stakes, creative work, learning, etc.).

### 5. Obsidian Report
Comprehensive markdown file in `automation-decisions/YYYYMMDD-task-slug.md`.

## 📝 The 4 Scoring Dimensions

### Frequency (0-5)
- **5**: Multiple times per day
- **3**: Weekly
- **1**: Monthly
- **0**: Rarely/one-time

### Time (0-5)
- **5**: Hours (2+)
- **3**: 30-120 minutes
- **1**: 5-30 minutes
- **0**: Under 5 minutes

### Error Cost (1-5)
- **5**: Catastrophic (legal, revenue impact)
- **3**: Annoying (delays, manual fix)
- **1**: Negligible (easy to fix)

### Longevity (0-5)
- **5**: Years (core process)
- **3**: Months (project-specific)
- **1**: Weeks (temporary)
- **0**: One-time

**Formula**: `Score = Frequency × Time × Error Cost × Longevity`

## 🎨 Example Scenarios

### ✅ Automate: Invoice Generation
- Frequency: 3 (weekly)
- Time: 3 (30-120 min)
- Error Cost: 5 (client trust)
- Longevity: 5 (ongoing business)
- **Score: 225** → AUTOMATE NOW

### ❌ Don't Automate: Monthly Report
- Frequency: 1 (monthly)
- Time: 5 (2 hours)
- Error Cost: 1 (internal only)
- Longevity: 3 (months)
- **Score: 15** → STAY MANUAL

### 🤔 Maybe Automate: Social Media
- Frequency: 3 (weekly)
- Time: 1 (15 min)
- Error Cost: 3 (brand visibility)
- Longevity: 3 (testing channel)
- **Score: 27** → AUTOMATE IF EASY (< 4 hrs to build)

## 🛠️ Installation

### Prerequisites
```bash
pip3 install anthropic groq httpx
```

### Environment Variables
```bash
export ANTHROPIC_API_KEY="your-key"
export GROQ_API_KEY="your-key"  # Optional, for future voice features
```

### Verify Setup
```bash
cd ~/.claude/skills/automation-advisor
python3 test_demo.py  # Should show 4 examples
```

## 📂 Output Location

Reports saved to: `~/Brains/brain/automation-decisions/YYYYMMDD-task-slug.md`

Example: `20260124-invoice-generation.md`

## 🎓 Learn More

- [[Automation Decision Matrix]] - Full framework documentation
- [[Claude Code Lab 02]] - Workshop teaching this approach
- README.md - Complete technical documentation

## 🐛 Troubleshooting

### "Missing dependencies"
```bash
pip3 install anthropic groq httpx
```

### "Module not found: visualize"
Make sure you're running from the skill directory:
```bash
cd ~/.claude/skills/automation-advisor
python3 server.py --mode console
```

### "Permission denied"
```bash
chmod +x server.py test_demo.py visualize.py
```

## 🔮 Coming Soon

- [ ] Web server interface (port 8080)
- [ ] Voice input/output via Groq
- [ ] Claude Code skill command (`/automation-advisor`)
- [ ] Historical tracking (did automation pay off?)
- [ ] Template library for common automations

## 💡 Tips

1. **Run examples first**: See `test_demo.py` for 4 real scenarios
2. **Be honest with scores**: Don't inflate to justify automation
3. **Consider maintenance**: Factor in ongoing time cost
4. **Review decisions**: Revisit after 3-6 months to validate
5. **Trust the framework**: If score is low, don't automate

## 🤝 Philosophy

> "I *could* automate this" ≠ "I *should* automate this"

This framework helps you make the right call based on **data**, not excitement about automation.

Sometimes the right answer is "stay manual" - and that's okay!
