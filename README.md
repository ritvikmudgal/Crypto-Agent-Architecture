# AI-Driven PKI Lifecycle Management System

## Problem Statement

Modern digital infrastructure depends heavily on Public Key Infrastructure (PKI) for trust, identity, and secure communications. However, managing cryptographic keys and certificates is often messy, manual, and error-prone. This leads to:

- **Security risks**: Weak keys, expired certificates, inconsistent policies
- **Operational headaches**: Service outages from cert expiry, manual renewals, poor visibility
- **Compliance gaps**: Missing audit trails, policy violations, unclear accountability

Traditional solutions either rely on manual processes (error-prone) or rigid workflow engines (inflexible). We need something smarter—a system that can reason about cryptographic workflows while staying safely within security boundaries.

## Our Solution

An **AI-driven multi-agent architecture** where Claude orchestrates PKI operations through specialized agents. The key principle: **AI plans and validates, trusted tools execute crypto operations**.

The system handles:
- Key pair generation (RSA, ECC) via Vault/HSM
- CSR creation and validation using OpenSSL
- Certificate issuance, renewal, and revocation through CAs
- Policy enforcement as guardrails (key sizes, validity, usage)
- Asset inventory tracking and expiry monitoring
- Complete audit trails for compliance

## Project Structure

This repository contains documentation for the AI-driven PKI management architecture:

| File | Description | Link |
|------|-------------|------|
| **Architecture.md** | Complete system architecture with multi-agent design, orchestration flows, and security boundaries | [View](./pki_architecture.md) |
| **MCP.md** | Analysis of Model Context Protocol - whether to use it and why | [View](./MCP.md) |
| **Frameworks.md** | Evaluation of AI frameworks (LangChain, Graph RAG) and design decisions | [View](./Frameworks.md) |
| **MultiAgent.md** | Deep dive into multi-agent architecture benefits and trade-offs | [View](./MultiAgent.md) |
| **Result.md** | The Result of this assignment with code examples and best practices | [View](./Result.md) |
| **Tools.md** | Tools used in the implementation | [View](./Tools.md) |
| **Workflows.md** | The workflows and orchestration logic | [View](./Workflows.md) |
| **Policies.md** | Policies and validation rules | [View](./Policies.md) |
| **bedrock_agent-aws.py** | The running Agent for cryptography using python and AWS Bedrock | [View](./bedrock_agent-aws.py) |


## POC
A proof-of-concept implementation is available in the `bedrock_agent-aws.py` file. It includes: 
- Basic Claude API integration
- Sample workflows for key generation, CSR creation, and certificate issuance
- A dummy policy enforcement example
- Interactive chat interface for testing
- Sample agents for key generation, CSR creation, certificate issuance

## Core Principles

1. **AI orchestrates, never executes crypto**: Claude plans workflows but never touches private keys or performs cryptographic math
2. **Policy as guardrails**: Security rules enforced programmatically before any operation
3. **Separation of concerns**: Each agent has a single, well-defined responsibility
4. **Audit everything**: Immutable logs for every decision and action
5. **Use battle-tested tools**: Rely on OpenSSL, Vault, established CAs—don't reinvent crypto

## Key Benefits

- **Security**: No crypto in AI layer, policy enforcement at every step
- **Flexibility**: Natural language interface for complex operations
- **Reliability**: Automated renewals, proactive expiry monitoring
- **Compliance**: Complete audit trails, policy version tracking
- **Extensibility**: Easy to add new agents (e.g., post-quantum migration)

## Technologies Used

- **Agent Layer**: Claude API (Sonnet 4)
- **Key Management**: HashiCorp Vault / AWS KMS
- **Crypto Operations**: OpenSSL
- **Certificate Authority**: Internal CA or ACME
- **Storage**: PostgreSQL for inventory
- **Audit**: CloudWatch / Splunk for immutable logs

## Why This Matters

This isn't just about automating PKI—it's about showing how AI agents can safely handle security-critical operations when properly constrained. The architecture demonstrates:

- How to keep AI away from sensitive operations while still being useful
- When to use (and not use) popular AI frameworks
- How multi-agent design improves auditability and testability
- How to build enterprise-grade systems with AI orchestration

## Getting Started

Read the documentation in order:
1. This README (you are here)
2. [Architecture.md](./Architecture.md) - System design
3. [Workflows.md](./Workflows.md) - Orchestration flows
4. [Policies.md](./Policies.md) - Security rules
5. [Tools.md](./Tools.md) - Tools used
6. [Result.md](./Result.md) - How to build it
7. [Running Agent](./bedrock_agent-aws.py) - POC- Running Agent for cryptography using python and AWS Bedrock



