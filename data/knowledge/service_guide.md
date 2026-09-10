# Service Guide

The chat platform separates synchronous request-response chat from long-running job processing.
Short LLM requests are protected by a semaphore so downstream concurrency remains bounded.
Long-running work is accepted as a job, placed in a bounded queue, and processed by workers.

The service exposes polling, Server-Sent Events, and WebSocket endpoints so their delivery cost can be compared under the same workload.

Grounded knowledge queries retrieve local documents first. If retrieval confidence is below the configured threshold, the system returns a no-context response instead of asking the language model to invent an answer.
