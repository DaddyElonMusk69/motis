# Motis Operator System Documentation

The Operator System is the core trading framework within Motis. Operators are autonomous agents capable of managing entire trading lifecycles. They define strategy execution logic using a modular Node system and can operate universally across different storage and database modes. 

Due to the length and comprehensiveness of the operator system design, the documentation has been chunked logically. 

## Reading Order

| Chapter | Content |
|---|---|
| [1. Architecture Overview](./01-architecture-overview.md) | High-level foundational choices, the 3 storage modes (Dev, Platform, Standalone), Registry rules, mode configurations, migration paths. |
| [2. Contract and Validation](./02-contract-and-validation.md) | Node roles (REASON, EXECUTE, GUARD, Compute, DATA), building a validated DAG graph, Risk Guard rules, Operator testing/Quality Gate checklist. |
| [3. SDK and Execution Engines](./03-sdk-and-execution.md) | Building and validating REASON / execution paths, SDK helpers, MCP configurations and usage, execution flow variations (linear, fan-out, fan-in), prompt updates and code examples. |
| [4. Workflow and Reference Appendices](./04-workflow-and-appendix.md) | Master agent operator authoring logic, overall build flowchart, Database initialization templates for Operators and Operator Runs/Logs. |
| [Configuration Guide](./configuration-guide.md) | Guide details how configuring modes alter `.env` settings depending on mode (platform, dev, standalone). |
