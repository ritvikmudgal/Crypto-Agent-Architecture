# AI Framework Analysis

## Overview

This document evaluates popular AI frameworks and tools for our PKI lifecycle management system. We examine whether to use LangChain, Graph-based RAG, and other frameworks—or build with direct Claude API calls.

**BUT** We intentionally avoid most frameworks. Here's why.

---

## LangChain

### What is LangChain?

LangChain is a framework for building LLM applications. It provides:
- Agent orchestration and tool chaining
- Memory management
- Prompt templates
- Pre-built integrations with many services

### Should We Use It?

### Decision: **NO** ❌

### Why NOT Use LangChain?

#### 1. **Too Much Abstraction for Security-Critical Systems**

**The Problem**: LangChain adds multiple layers between your code and the LLM.

```
Your Code → LangChain Agent → LangChain Memory → LangChain Tools → Claude → OpenSSL/Vault

vs.

Your Code → Claude API → OpenSSL/Vault
```

**Why it matters**:
- Hard to audit exactly what prompt was sent
- Difficult to trace which tool was called when
- Memory management introduces non-determinism
- Debugging involves understanding LangChain internals

For PKI operations where every action must be auditable, this abstraction is dangerous.

#### 2. **State Management Introduces Non-Determinism**

**The Problem**: LangChain's memory systems remember context across calls.

```python
# LangChain approach (with memory)
agent = initialize_agent(tools, llm, memory=ConversationBufferMemory())
agent.run("Issue a cert for api.example.com")
# Memory remembers this
agent.run("Do it again")  # What does "it" mean? Same params?
```

For crypto operations, this is risky:
- What if policy changed between calls?
- What if "it" refers to outdated parameters?
- How do you audit what the agent "remembered"?

**Our approach** (stateless):
```python
# Direct Claude API (stateless)
response = claude.messages.create(
    model="claude-sonnet-4",
    messages=[{
        "role": "user",
        "content": "Issue cert: api.example.com, RSA 4096, 90 days"
    }]
)
# Every request is explicit and self-contained
```

#### 3. **Vendor Lock-In**

**The Problem**: Tight coupling to LangChain's abstractions.

If you want to:
- Switch from Claude to another LLM
- Change how tools are invoked
- Modify memory behavior
- Add custom logging

You're fighting against LangChain's opinions. Our direct API approach:
- Swap Claude for another model (just change endpoint)
- Tool invocation is our code (easy to modify)
- No memory to manage
- Custom logging at every step

#### 4. **Debugging is a Nightmare**

**The Problem**: When something fails, where did it fail?

```
LangChain traceback:
  File "langchain/agents/agent.py", line 1234
  File "langchain/memory/buffer.py", line 567
  File "langchain/tools/base.py", line 890
  ... your code somewhere in here ...
```

vs. our approach:
```
Direct API traceback:
  File "your_orchestrator.py", line 42
  File "your_policy_agent.py", line 67
  ... clear path from error to your code ...
```

### Where LangChain COULD Be Useful

LangChain shines in:
- **Rapid prototyping**: Get a chatbot up quickly
- **Non-critical applications**: Customer service bots, content generation
- **When abstraction helps**: Building many similar agents with common patterns

But for PKI: **Security > Convenience**

---

## Graph-based RAG (Retrieval-Augmented Generation)

### What is Graph RAG?

Graph RAG uses knowledge graphs to store and retrieve contextual information for LLMs. Instead of vector embeddings, it models relationships:

```
Certificate --[issued_by]--> CA
Certificate --[uses_key]--> Private_Key
Certificate --[expires]--> Date
Private_Key --[algorithm]--> RSA-4096
```

### Should We Use It?

### Decision: **NO** (for core operations) ❌

### Why NOT Use Graph RAG?

#### 1. **We Already Have a Relational Database**

**The Problem**: Graph RAG solves a problem we don't have.

Our Inventory Agent uses PostgreSQL:
```sql
CREATE TABLE certificates (
    cert_id UUID PRIMARY KEY,
    key_id UUID REFERENCES keys(key_id),
    ca_id UUID REFERENCES certificate_authorities(ca_id),
    subject TEXT,
    expiry TIMESTAMP,
    ...
);
```

This handles relationships perfectly:
- Foreign keys for cert → key relationships
- Indexes for fast lookups
- ACID guarantees for consistency
- SQL for complex queries

Why add a graph layer on top?

#### 2. **Policy Rules Are Code, Not Knowledge**

**The Problem**: Graph RAG is for semantic search, not deterministic rules.

Our policies are:
```json
{
  "min_key_size_rsa": 3072,
  "max_validity_days": 397,
  "allowed_ekus": ["serverAuth", "clientAuth"]
}
```

These are programmatic rules, not knowledge to retrieve. We don't need to search for them—we just evaluate them.

#### 3. **No Need for Semantic Search**

**The Problem**: Graph RAG excels at queries like "find similar certificates" or "what's related to this CA?"

But our queries are specific:
- "Get cert by serial number" (indexed lookup)
- "Find certs expiring in 30 days" (date range query)
- "List all certs for api.example.com" (exact match)

SQL handles these better than graph traversal.

#### 4. **Adds Latency with No Clear Benefit**

Graph RAG workflow:
```
Request → Build graph query → Traverse graph → LLM synthesis → Response
```

Our workflow:
```
Request → SQL query → Direct response
```

For operational workflows (issue cert, renew, revoke), speed matters. Graph RAG adds overhead.

### Where Graph RAG COULD Be Useful

Graph RAG would make sense if we added:

**Compliance Q&A System**:
```
Question: "What certificates are affected by new NIST guidelines?"

Graph RAG:
NIST_Guideline --[requires]--> RSA_3072
RSA_3072 --[incompatible_with]--> Old_Certificates
Old_Certificates --[includes]--> [List of certs]
```

**Certificate Discovery**:
```
Question: "Show me all infrastructure related to our payments service"

Graph RAG:
Payments_Service --[uses]--> Load_Balancer
Load_Balancer --[has_cert]--> TLS_Certificate
TLS_Certificate --[signed_by]--> Internal_CA
```

But for core operations (issue, renew, revoke), it's overkill.

---

## Other Frameworks Considered

### AutoGen (Microsoft)

**What it does**: Multi-agent conversation framework

**Decision**: NO ❌
- **Why**: Too chatty for deterministic crypto operations. Agents "negotiate" solutions—we want predictable execution.
- **Good for**: Collaborative problem-solving, creative tasks
- **Bad for**: Security-critical operations needing determinism

### CrewAI

**What it does**: Role-based multi-agent system

**Decision**: NO ❌
- **Why**: Similar to our multi-agent design but adds framework overhead
- **Our approach**: Direct Claude API with custom agent logic (more control)
- **CrewAI benefit**: Pre-built patterns for agent collaboration
- **Our benefit**: Full visibility and auditability

### Semantic Kernel (Microsoft)

**What it does**: Enterprise AI orchestration

**Decision**: NO ❌
- **Why**: Heavy framework for relatively simple PKI workflows
- **Good for**: Complex enterprise applications with many integrations
- **Our case**: Direct API calls are cleaner and easier to audit

---

## What We Actually Use

### Direct Claude API + Custom Tool Definitions

```python
# Our approach: Explicit, auditable, simple

import anthropic

client = anthropic.Anthropic()

def orchestrator_agent(request):
    response = client.messages.create(
        model="claude-sonnet-4",
        messages=[{
            "role": "user",
            "content": request
        }],
        tools=[
            {
                "name": "check_policy",
                "description": "Validate request against security policy",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "algorithm": {"type": "string"},
                        "key_size": {"type": "integer"},
                        "validity_days": {"type": "integer"}
                    }
                }
            },
            {
                "name": "generate_key",
                "description": "Generate key pair in Vault",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "algorithm": {"type": "string"},
                        "key_size": {"type": "integer"}
                    }
                }
            }
            # ... more tools
        ]
    )
    
    # Log everything
    log_to_audit_trail(response)
    
    # Handle tool calls
    if response.stop_reason == "tool_use":
        for tool_call in response.content:
            if tool_call.type == "tool_use":
                result = execute_tool(tool_call.name, tool_call.input)
                # Continue conversation with tool result
                
    return response
```

**Advantages**:
- ✅ Full control over every interaction
- ✅ Easy to audit (log every request/response)
- ✅ No hidden state or memory
- ✅ Simple to debug
- ✅ No framework dependencies

---

## Framework Comparison Table

| Framework | Use It? | Reason |
|-----------|---------|--------|
| **LangChain** | ❌ NO | Too much abstraction, hard to audit, state management issues |
| **Graph RAG** | ❌ NO (core ops) | SQL handles relationships better for our use case |
| **AutoGen** | ❌ NO | Non-deterministic agent negotiation inappropriate for crypto |
| **CrewAI** | ❌ NO | Similar to our design but less control |
| **Semantic Kernel** | ❌ NO | Heavyweight for our relatively simple workflows |
| **Direct Claude API** | ✅ YES | Full control, auditability, simplicity |

---

## When to Use Frameworks vs. Direct API

### Use Frameworks When:
- Rapid prototyping needed
- Application is non-critical
- Abstraction genuinely simplifies code
- Many common patterns across agents
- Trading control for speed of development

### Use Direct API When:
- Security-critical operations
- Full auditability required
- Deterministic behavior needed
- Debugging clarity important
- Custom logic doesn't fit framework patterns

**For PKI**: We need security, auditability, and determinism. Direct API wins.

---

## Architecture Impact

```
┌────────────────────────────────────────────────┐
│  Framework-Heavy Approach (NOT USED)           │
├────────────────────────────────────────────────┤
│                                                │
│  Request → LangChain Agent                    │
│              ↓                                 │
│          LangChain Memory                      │
│              ↓                                 │
│          LangChain Tools                       │
│              ↓                                 │
│          Claude API                            │
│              ↓                                 │
│          Crypto Tools                          │
│                                                │
│  Many layers, hard to audit, non-deterministic│
│                                                │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  Direct API Approach (OUR DESIGN)              │
├────────────────────────────────────────────────┤
│                                                │
│  Request → Orchestrator Agent                 │
│              ↓                                 │
│          Claude API                            │
│              ↓                                 │
│          Specialized Agents                    │
│              ↓                                 │
│          Crypto Tools                          │
│                                                │
│  Clear path, fully auditable, deterministic   │
│                                                │
└────────────────────────────────────────────────┘
```

---

## Key Takeaways

1. **Frameworks add value for rapid prototyping**, but PKI needs careful engineering
2. **Abstraction is the enemy of auditability** in security systems
3. **Direct API calls are simpler** for our relatively straightforward workflows
4. **State management in frameworks** introduces non-determinism we can't accept
5. **SQL > Graph RAG** for our specific relationship tracking needs

## Final Verdict

```
┌─────────────────────────────────────────────┐
│  AI Frameworks for PKI Management           │
│                                             │
│  LangChain:      NOT USED                   │
│  Graph RAG:      NOT USED (core ops)        │
│  AutoGen:        NOT USED                   │
│  CrewAI:         NOT USED                   │
│                                             │
│  Direct Claude API: ✅ USED                 │
│                                             │
│  Reason: Security and auditability require  │
│          full control and determinism       │
│                                             │
└─────────────────────────────────────────────┘
```

**We choose simplicity, control, and auditability over framework convenience.**