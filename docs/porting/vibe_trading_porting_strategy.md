# Vibe Trading → MOTIS Porting Strategy

**Date:** 2026-04-10  
**Status:** Implementation Guide

---

## Overview

You're correct — the porting is straightforward because Vibe Trading's architecture maps cleanly onto MOTIS's design:

```
Vibe Trading Component          →    MOTIS Component
─────────────────────────────────────────────────────────────
Skills (SKILL.md files)         →    Master Agent Skills (in-process)
Tools (Python functions)        →    Master Agent Tools (in-process)
Swarm Presets (YAML configs)    →    ResearchOperator Presets
Backtest Engine                 →    BacktestOperator Engine
Signal Engines (Python)         →    Operator Node Functions
```

---

## 1. Skills → Master Agent Skills

### What They Are

Vibe Trading skills are **markdown prompts** (`SKILL.md`) that get loaded into the agent's context when referenced. They're not executable code — they're **instructions** for the LLM.

### How to Port

**Super easy — just copy the files:**

```bash
# Example: Port the technical-basic skill
cp services/agent/upstream/vibe_trading/agent/src/skills/technical-basic/SKILL.md \
   services/agent/motis_agent/skills/finance/analysis/technical_basic.md
```

**That's it.** The Master Agent's skill loader will:
1. Discover the `.md` file
2. Parse the frontmatter (name, category, description)
3. Load the content into context when the agent needs it

### Skill Registry Auto-Discovery

```python
# In services/agent/motis_agent/core/skills.py
class SkillRegistry:
    def discover_skills(self, base_path: Path):
        """Auto-discover all SKILL.md files"""
        for skill_file in base_path.rglob("*.md"):
            skill = self._parse_skill(skill_file)
            self.register(skill)
```

**The agent gains the skill automatically** — no code changes needed.

### Example: How the Agent Uses Skills

```
User: "Analyze BTC using Smart Money Concepts"

Agent thinks:
  → User mentioned "Smart Money Concepts"
  → I have a skill called "smc"
  → Load skill content into my context
  → Now I know: BOS, ChoCH, FVG, order blocks
  → Generate analysis using that framework
```

### Porting Checklist for Skills

- [ ] Copy `SKILL.md` to `services/agent/motis_agent/skills/finance/<category>/`
- [ ] Rename file to match MOTIS naming convention (underscores, not hyphens)
- [ ] Verify frontmatter has `name`, `category`, `description`
- [ ] If skill has `example_signal_engine.py`, port separately (see Section 4)
- [ ] Test: Agent can reference the skill in conversation

**Effort:** 5 minutes per skill (mostly file copying)

---

## 2. Tools → Master Agent Tools

### What They Are

Vibe Trading tools are **Python functions** that the agent can call during its ReAct loop. Examples:
- `pattern_tool.py` — detect candlestick patterns
- `factor_analysis_tool.py` — compute alpha factors
- `options_pricing_tool.py` — Black-Scholes calculator

### How to Port

**Copy the Python file and register it:**

```python
# 1. Copy the tool file
cp services/agent/upstream/vibe_trading/agent/src/tools/pattern_tool.py \
   services/agent/motis_agent/tools/pattern.py

# 2. Add MIT license header
# 3. Adapt imports if needed
# 4. Register in tool registry
```

### Tool Registration

```python
# In services/agent/motis_agent/tools/_registry.py
from motis_agent.tools.pattern import PatternTool

TOOL_REGISTRY = {
    "pattern_recognition": PatternTool(),
    "factor_analysis": FactorAnalysisTool(),
    "options_pricing": OptionsPricingTool(),
    # ... etc
}
```

**The agent gains the tool automatically** — it appears in the agent's tool list.

### Example: How the Agent Uses Tools

```
User: "Find candlestick patterns in BTC daily chart"

Agent ReAct loop:
  Thought: I need to detect candlestick patterns
  Action: pattern_recognition
  Action Input: {"symbol": "BTC-USDT", "timeframe": "1d", "patterns": "all"}
  Observation: [Doji at 2024-04-08, Hammer at 2024-04-05, ...]
  Thought: I found 3 bullish patterns
  Final Answer: "BTC shows bullish reversal patterns..."
```

### Porting Checklist for Tools

- [ ] Copy tool file to `services/agent/motis_agent/tools/`
- [ ] Add MIT license attribution header
- [ ] Update imports (if tool depends on Vibe Trading internals)
- [ ] Register in `_registry.py`
- [ ] Add tool schema (name, description, parameters) for LLM
- [ ] Test: Agent can call the tool successfully

**Effort:** 30 minutes per tool (includes testing)

---

## 3. Swarm Presets → ResearchOperator Presets

### What They Are

Swarm presets are **YAML configurations** that define multi-agent research teams. Each preset specifies:
- Agent roles (bull analyst, bear analyst, risk officer, etc.)
- System prompts for each agent
- Task dependencies (parallel or sequential)
- Required variables (target, timeframe, market)

### How to Port

**Copy the YAML file — it works as-is:**

```bash
# Example: Port the crypto trading desk preset
cp services/agent/upstream/vibe_trading/agent/config/swarm/crypto_trading_desk.yaml \
   services/agent/motis_agent/swarms/presets/crypto_trading_desk.yaml
```

**That's it.** The ResearchOperator will:
1. Load the YAML preset
2. Spawn N agents (one per role)
3. Run tasks in dependency order
4. Synthesize results

### ResearchOperator Architecture

```python
# ResearchOperator wraps SwarmRunner in a LangGraph graph
class ResearchState(TypedDict):
    prompt: str
    swarm_preset: str              # e.g., "crypto_trading_desk"
    per_agent_outputs: dict        # {agent_id: output}
    synthesis: str                 # final brief
    report_url: str                # S3 link

graph = StateGraph(ResearchState)
graph.add_node("configure_swarm", configure_swarm_node)
graph.add_node("run_swarm_agents", run_swarm_agents_node)  # SwarmRunner here
graph.add_node("synthesize", synthesize_node)
graph.add_node("persist_brief", persist_brief_node)
graph.add_node("notify_user", notify_user_node)
```

### How the Master Agent Uses Swarms

```
User: "Research BTC from multiple perspectives"

Master Agent:
  → Recognizes this as a research request
  → Creates a ResearchOperator with preset="crypto_trading_desk"
  → Invokes the operator via operator_invoke tool
  → Operator runs async, streams per-agent outputs to chat
  → Results persisted to DB + S3
  → User sees "Research complete" with link to full brief
```

### Key Difference from Vibe Trading

**Vibe Trading:** Swarms run inline in the agent loop (blocking)  
**MOTIS:** Swarms run as ResearchOperators (persistent, schedulable, visible in sidebar)

This means:
- Research results are **persisted** (not lost after conversation ends)
- Research can be **scheduled** (e.g., "run BTC macro brief every Sunday")
- Research briefs can **feed other operators** (LiveTradeOperator reads latest brief)
- Research is **visible in UI** (sidebar shows "Research running..." → "Complete")

### Porting Checklist for Swarm Presets

- [ ] Copy YAML file to `services/agent/motis_agent/swarms/presets/`
- [ ] Verify all referenced skills exist in MOTIS skill registry
- [ ] Test: ResearchOperator can load and run the preset
- [ ] Verify per-agent outputs stream correctly to frontend
- [ ] Verify synthesis node produces coherent final brief

**Effort:** 10 minutes per preset (mostly verification)

---

## 4. Signal Engines → Operator Node Functions

### What They Are

Some Vibe Trading skills include `example_signal_engine.py` — **deterministic Python functions** that generate trading signals without LLM reasoning.

Example from `smc/example_signal_engine.py`:
```python
def smc_signal(df: pd.DataFrame, swing_length: int = 10) -> pd.Series:
    """
    Returns: pd.Series with values 1 (long), -1 (short), 0 (neutral)
    """
    bos = detect_bos(df, swing_length)
    choch = detect_choch(df, swing_length)
    fvg = detect_fvg(df)
    
    signal = pd.Series(0, index=df.index)
    signal[(bos == 1) & (fvg == 1)] = 1   # Bullish
    signal[(bos == -1) & (fvg == -1)] = -1  # Bearish
    return signal
```

### How to Port

**Extract the function and use it in operator nodes:**

```python
# 1. Copy signal engine to skills/finance/analysis/
cp services/agent/upstream/vibe_trading/agent/src/skills/smc/example_signal_engine.py \
   services/agent/motis_agent/skills/finance/analysis/smc_signals.py

# 2. Import in operator node
from motis_agent.skills.finance.analysis.smc_signals import smc_signal

# 3. Use in LiveTradeOperator node
def generate_signals_node(state: OperatorState) -> OperatorState:
    df = state["market_data"]
    signals = smc_signal(df, swing_length=10)  # Deterministic, no LLM
    state["signals"] = signals
    return state
```

### Key Insight

**Signal engines are NOT agent skills** — they're **operator node functions**.

- **Agent skills** (SKILL.md) → Master Agent uses for reasoning
- **Signal engines** (Python) → Operators use for deterministic signal generation

### Porting Checklist for Signal Engines

- [ ] Copy signal engine to `skills/finance/analysis/<name>_signals.py`
- [ ] Add MIT license header
- [ ] Ensure function signature is clean (takes DataFrame, returns signals)
- [ ] Write unit tests (verify signal logic on sample data)
- [ ] Document parameters and return format
- [ ] Use in operator node (no LLM call needed)

**Effort:** 1 hour per signal engine (includes testing)

---

## 5. Backtest Engine → BacktestOperator

### What It Is

Vibe Trading's backtest engine is a **multi-market backtesting framework** with:
- 4 engines (crypto, global equity, China A-shares, options)
- 5 data loaders (CCXT, yfinance, akshare, tushare, OKX)
- 4 portfolio optimizers (risk parity, mean-variance, etc.)
- Metrics calculator (Sharpe, Sortino, max drawdown, etc.)

### How to Port

**Copy the entire backtest directory and wrap it in a LangGraph operator:**

```bash
# 1. Copy backtest engine
cp -r services/agent/upstream/vibe_trading/agent/backtest/ \
      services/agent/motis_agent/backtest/

# 2. Add MIT license headers to all files
# 3. Update imports
# 4. Wrap in BacktestOperator
```

### BacktestOperator Architecture

```python
class BacktestState(TypedDict):
    strategy_config: dict          # User's strategy config
    market_data: pd.DataFrame      # Loaded by data loader
    backtest_results: dict         # Metrics from engine
    ai_critique: str               # Model analyzes results
    report_url: str                # S3 link to full report

graph = StateGraph(BacktestState)
graph.add_node("parse_strategy", parse_strategy_node)
graph.add_node("load_data", load_data_node)           # Uses Vibe Trading loaders
graph.add_node("run_engine", run_engine_node)         # Uses Vibe Trading engines
graph.add_node("calculate_metrics", metrics_node)     # Uses Vibe Trading metrics
graph.add_node("ai_critique", ai_critique_node)       # NEW: Model analyzes results
graph.add_node("persist_report", persist_report_node)
```

### Key Addition: AI Critique Node

**Vibe Trading:** Backtest → metrics → done  
**MOTIS:** Backtest → metrics → **AI critique** → suggestions

```python
def ai_critique_node(state: BacktestState) -> BacktestState:
    """Model analyzes backtest results and suggests improvements"""
    results = state["backtest_results"]
    
    prompt = f"""
    Backtest Results:
    - Sharpe: {results['sharpe']}
    - Max Drawdown: {results['max_drawdown']}%
    - Win Rate: {results['win_rate']}%
    
    Analyze failure modes and suggest improvements.
    """
    
    critique = model.generate(prompt)  # LLM call
    state["ai_critique"] = critique
    return state
```

This is a **PRD requirement** — the BacktestOperator must provide actionable feedback.

### How the Master Agent Uses Backtest

```
User: "Backtest my BTC funding rate arb strategy"

Master Agent:
  → Creates a BacktestOperator with user's strategy config
  → Invokes operator via operator_invoke tool
  → Operator runs async:
      1. Loads BTC data (via CCXT loader)
      2. Runs crypto engine
      3. Calculates metrics
      4. AI critiques results
      5. Persists report to S3
  → User sees: "Sharpe 1.8, Max DD 12%, Win Rate 65%"
  → User sees: "AI Critique: Strategy performs well in trending markets
                but suffers in choppy conditions. Consider adding a
                volatility filter to avoid low-conviction trades."
```

### Porting Checklist for Backtest Engine

- [ ] Copy entire `backtest/` directory
- [ ] Add MIT license headers
- [ ] Update imports (remove Vibe Trading-specific paths)
- [ ] Test each engine independently (crypto, equity, options)
- [ ] Test each loader independently (CCXT, yfinance, akshare)
- [ ] Wrap in BacktestOperator LangGraph
- [ ] Implement AI critique node
- [ ] Test end-to-end: config → results → critique → report
- [ ] Verify report persists to S3 and attaches to operator spec

**Effort:** 2-3 days (includes testing and AI critique implementation)

---

## 6. Porting Effort Summary

| Component | Count | Effort per Item | Total Effort | Priority |
|-----------|-------|-----------------|--------------|----------|
| **Skills** | 64 | 5 min | ~5 hours | High |
| **Tools** | 5 (high-priority) | 30 min | ~2.5 hours | High |
| **Swarm Presets** | 29 | 10 min | ~5 hours | Critical |
| **Signal Engines** | 14 | 1 hour | ~14 hours | Medium |
| **Backtest Engine** | 1 | 2-3 days | ~20 hours | Critical |
| **Total** | 113 items | — | **~47 hours** | — |

**Realistic timeline:** 1-2 weeks for one developer (with testing)

---

## 7. Phased Porting Plan

### Phase 0 (Week 1) — Foundation

**Goal:** Master Agent can use skills, ResearchOperator can run swarms, BacktestOperator can backtest

**Tasks:**
1. Port all 64 skills (5 hours)
   - Copy SKILL.md files to `skills/finance/`
   - Verify skill registry auto-discovery works
   - Test: Agent can reference skills in conversation

2. Port 29 swarm presets (5 hours)
   - Copy YAML files to `swarms/presets/`
   - Verify ResearchOperator can load presets
   - Test: Run `crypto_trading_desk` preset end-to-end

3. Port backtest engine (20 hours)
   - Copy `backtest/` directory
   - Wrap in BacktestOperator
   - Implement AI critique node
   - Test: Backtest BTC strategy end-to-end

**Deliverable:** Master Agent has 64 skills, ResearchOperator has 29 presets, BacktestOperator works

---

### Phase 1 (Week 2) — Tools & Signal Engines

**Goal:** Master Agent has high-value tools, Operators have signal engines

**Tasks:**
1. Port 5 high-priority tools (2.5 hours)
   - `pattern_tool` → `tools/pattern.py`
   - `factor_analysis_tool` → `tools/factor.py`
   - `options_pricing_tool` → `tools/options.py`
   - Register in tool registry
   - Test: Agent can call each tool

2. Port 14 signal engines (14 hours)
   - Extract from skills to `skills/finance/analysis/<name>_signals.py`
   - Write unit tests
   - Document usage
   - Test: Use in operator nodes

**Deliverable:** Master Agent has pattern/factor/options tools, Operators have 14 signal engines

---

### Phase 2 (Ongoing) — Refinement

**Goal:** Polish, optimize, add remaining tools

**Tasks:**
1. Port remaining tools as needed (medium/low priority)
2. Add more signal engines as operators require them
3. Optimize swarm presets based on user feedback
4. Add custom swarm presets for MOTIS-specific use cases

---

## 8. Key Architectural Decisions

### Decision 1: Skills are In-Process, Not MCP

**Vibe Trading:** Skills are markdown files loaded by the agent  
**MOTIS:** Same — skills are in-process, not MCP tools

**Reason:** Skills are **context**, not **execution**. They don't need network isolation.

---

### Decision 2: Swarms are Operators, Not Inline

**Vibe Trading:** Swarms run inline in the agent loop (blocking)  
**MOTIS:** Swarms run as ResearchOperators (persistent, schedulable)

**Reason:** Per PRD, research must be:
- Persistent (results don't disappear)
- Schedulable (e.g., weekly macro brief)
- Referenceable (other operators read research briefs)
- Visible in UI (sidebar shows research status)

---

### Decision 3: Backtest is an Operator, Not a Tool

**Vibe Trading:** Backtest is a tool the agent calls  
**MOTIS:** Backtest is a BacktestOperator (persistent, results attached to operator spec)

**Reason:** Per PRD, backtest results must:
- Persist to DB + S3
- Attach to operator spec (displayed in sidebar and marketplace)
- Include AI critique (model analyzes results)
- Be referenceable (user reviews backtest days later)

---

### Decision 4: Signal Engines are Operator Functions, Not Agent Skills

**Vibe Trading:** Signal engines are example code in skill directories  
**MOTIS:** Signal engines are standalone functions called by operator nodes

**Reason:** Operators need **deterministic** signal generation (no LLM reasoning). Signal engines provide this.

---

## 9. Testing Strategy

### Skill Testing

```python
# Test: Agent can reference skill
def test_agent_uses_smc_skill():
    agent = MotisAgentLoop(user_context)
    response = agent.run("Analyze BTC using Smart Money Concepts")
    assert "BOS" in response or "ChoCH" in response  # Skill was loaded
```

### Tool Testing

```python
# Test: Agent can call tool
def test_agent_calls_pattern_tool():
    agent = MotisAgentLoop(user_context)
    response = agent.run("Find candlestick patterns in BTC daily")
    assert "pattern_recognition" in agent.tool_calls  # Tool was invoked
```

### Swarm Testing

```python
# Test: ResearchOperator runs preset
def test_research_operator_crypto_desk():
    operator = ResearchOperator(
        preset="crypto_trading_desk",
        variables={"target": "BTC-USDT", "timeframe": "swing 1-2 weeks"}
    )
    result = operator.run()
    assert result["synthesis"]  # Final brief exists
    assert len(result["per_agent_outputs"]) == 4  # 4 agents ran
```

### Backtest Testing

```python
# Test: BacktestOperator runs end-to-end
def test_backtest_operator_btc():
    operator = BacktestOperator(
        strategy="smc",
        symbols=["BTC-USDT"],
        timeframe="1h",
        start_date="2024-01-01",
        end_date="2024-12-31"
    )
    result = operator.run()
    assert result["backtest_results"]["sharpe"]  # Metrics exist
    assert result["ai_critique"]  # AI critique exists
    assert result["report_url"]  # Report persisted
```

---

## 10. Success Criteria

### Phase 0 Complete When:
- [ ] Master Agent can reference all 64 skills in conversation
- [ ] ResearchOperator can run all 29 swarm presets
- [ ] BacktestOperator can backtest crypto strategies end-to-end
- [ ] AI critique node provides actionable feedback
- [ ] All results persist to DB + S3

### Phase 1 Complete When:
- [ ] Master Agent can call pattern/factor/options tools
- [ ] Operators can use 14 signal engines for deterministic signals
- [ ] All tools and signal engines have unit tests
- [ ] Documentation exists for all ported components

---

## 11. Risk Mitigation

### Risk 1: Skill Dependencies

**Problem:** Some skills reference other skills (e.g., `load_skill("technical-basic")`)

**Mitigation:**
- Port skills in dependency order
- Verify all referenced skills exist before testing
- Add skill dependency graph to documentation

---

### Risk 2: Tool Import Errors

**Problem:** Tools may depend on Vibe Trading-specific imports

**Mitigation:**
- Review imports before copying
- Replace Vibe Trading paths with MOTIS paths
- Test each tool independently before registering

---

### Risk 3: Swarm Preset Skill References

**Problem:** Swarm presets reference skills that may not exist yet

**Mitigation:**
- Port all skills BEFORE testing swarm presets
- Add validation: ResearchOperator checks if all referenced skills exist
- Fail gracefully with clear error message if skill missing

---

### Risk 4: Backtest Engine Data Loader Failures

**Problem:** Data loaders may fail (network issues, API changes, etc.)

**Mitigation:**
- Implement auto-fallback (already in Vibe Trading's `registry.py`)
- Add retry logic with exponential backoff
- Log failures and surface to user with actionable message

---

## 12. Next Steps

1. **Immediate (Today):**
   - Review this porting strategy with the team
   - Confirm phased approach aligns with MOTIS roadmap
   - Assign ownership (who ports what)

2. **Week 1 (Phase 0):**
   - Port all 64 skills
   - Port all 29 swarm presets
   - Port backtest engine + wrap in BacktestOperator
   - Test end-to-end: User → Agent → ResearchOperator → BacktestOperator

3. **Week 2 (Phase 1):**
   - Port 5 high-priority tools
   - Port 14 signal engines
   - Write tests for all ported components
   - Document usage patterns

4. **Ongoing:**
   - Refine based on user feedback
   - Add custom MOTIS-specific skills/presets
   - Optimize performance

---

**End of Porting Strategy**
