# Zapier Triggers API - Project Overview

**Project ID:** K1oUUDeoZrvJkVZafqHL_1761943818847
**Organization:** Zapier
**Last Updated:** 2025-11-11

## What We're Building

The Zapier Triggers API is a new infrastructure layer that enables any external system to send events to Zapier in real-time. This shifts Zapier from a polling-based model (checking for new data periodically) to a push-based, event-driven architecture where systems can actively notify Zapier the moment something happens.

## The Core Problem

Currently, Zapier integrations define their own triggers and mostly rely on polling - checking external systems every 15 minutes for new data. This creates latency and limits real-time automation. There's no centralized way for systems to "push" events directly to Zapier.

## Our Solution

We're building a unified Triggers API with three core capabilities:

1. **Event Ingestion (POST /events)**: A standardized REST endpoint where any system can send events with a simple API call
2. **Event Storage**: Durable persistence in DynamoDB ensuring no events are lost, with automatic 30-day expiration
3. **Event Delivery (GET /inbox)**: Zapier workflows can retrieve and consume events, then acknowledge them when processed

## Technology Stack

- **Backend**: Python 3.11 with FastAPI on AWS Lambda (serverless, auto-scaling)
- **Database**: Amazon DynamoDB for event storage with TTL and Streams
- **Queue**: Amazon SQS for reliable event processing with retry logic
- **API**: Amazon API Gateway with custom authorizers for authentication
- **Infrastructure**: Terraform for infrastructure as code, deployed via CI/CD

## Why This Matters

This enables **real-time, event-driven automation** and lays the foundation for agentic workflows where AI agents can react to events instantly and chain actions together. Instead of "check Gmail every 15 minutes," it becomes "Gmail notifies Zapier the instant an email arrives."

## Success Criteria

- 99.9% reliability for event ingestion
- <100ms p95 latency for API responses
- 10,000+ events/sec throughput capacity
- 10% adoption by existing Zapier integrations within 6 months
- Positive developer satisfaction (8/10 rating)

## Epic 1: Build Zapier Triggers API MVP

The MVP consists of 12 stories implementing:
- Core AWS infrastructure (VPC, Lambda, DynamoDB, API Gateway)
- Event ingestion, storage, and delivery endpoints
- Authentication and authorization with API keys
- Monitoring, logging, and alerting with CloudWatch
- Load testing and performance optimization
- Security hardening and compliance (GDPR, CCPA)
- Developer documentation and sample clients
- Beta launch with selected partners

## Current Phase

**Implementation Phase** - Using BMAD orchestration to iteratively develop stories via the SM → Dev → QA cycle until all Epic 1 stories are complete.
