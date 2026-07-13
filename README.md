<div align="center">

# 🚀 Bridgestone IT Agent

### Enterprise AI-Powered IT Support Platform

An intelligent IT support platform that automates troubleshooting, ticket management, IT operations, and enterprise workflows using Artificial Intelligence.

Built with **FastAPI**, **Next.js**, **Google Gemini**, **PostgreSQL**, **Redis**, **Docker**, and modern enterprise architecture.

---

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![Next.js](https://img.shields.io/badge/Next.js-15-black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![Redis](https://img.shields.io/badge/Redis-Latest-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Latest-blue)
![License](https://img.shields.io/badge/License-Private-red)

</div>

---

# 📌 Overview

Bridgestone IT Agent is an enterprise-grade AI-powered IT Service Management platform designed to simplify employee IT support.

Instead of traditional ticket systems, employees interact with an intelligent AI assistant capable of:

- Understanding issues
- Troubleshooting automatically
- Executing IT actions
- Creating ServiceNow tickets
- Routing requests
- Managing approvals
- Monitoring SLA
- Providing real-time updates

The platform is designed around modern enterprise architecture and supports production deployment using Docker.

---

# ✨ Features

## 🤖 AI IT Support

- Conversational AI Support
- Intent Detection
- AI Diagnosis
- Multi-step Troubleshooting
- Smart Ticket Creation
- Knowledge Base Search
- Context-aware Responses
- Confidence Scoring

---

## 🎫 Ticket Management

- Incident Creation
- Service Requests
- Priority Assignment
- SLA Monitoring
- Ticket Timeline
- Status Tracking
- Approval Workflow
- Assignment Engine

---

## ⚙️ IT Actions

- Password Change
- Software Installation
- Restart Services
- Device Health Check
- VPN Troubleshooting
- Outlook Troubleshooting
- SAP Support
- Printer Support

---

## 👨‍💼 Employee Portal

- AI Chat
- My Tickets
- Ticket History
- Device Information
- Knowledge Base
- Notifications

---

## 👨‍💼 Manager Portal

- Pending Approvals
- Team Requests
- Approval Workflow
- Request Inspection
- Audit Information

---

## 🛠️ Administrator Portal

- User Management
- ITSM Queue
- Enterprise Devices
- Analytics Dashboard
- Knowledge Base Management
- System Configuration

---

# 🏗 Enterprise Architecture

```
Employee

↓

Next.js Frontend

↓

Nginx Reverse Proxy

↓

FastAPI Backend

↓

──────────────────────────────────────

Gemini AI

Knowledge Base

Business Logic

Authentication

Ticket Engine

Workflow Engine

↓

──────────────────────────────────────

PostgreSQL

Redis

↓

──────────────────────────────────────

ServiceNow

Microsoft Graph

Azure AD

Device Agent

```

---

# 🛠 Technology Stack

## Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS

---

## Backend

- FastAPI
- Python
- SQLAlchemy
- JWT Authentication

---

## Artificial Intelligence

- Google Gemini
- Prompt Engineering
- AI Troubleshooting
- Knowledge Retrieval

---

## Database

- PostgreSQL
- SQLite (Development)

---

## Cache

- Redis

---

## Infrastructure

- Docker
- Docker Compose
- Nginx

---

## Monitoring

- Prometheus
- Grafana

---

# 📂 Project Structure

```
bridgestone-it-agent/

├── frontend/
├── backend/
├── device-agent/
├── infrastructure/
│   ├── docker/
│   ├── compose/
│   ├── nginx/
│   └── monitoring/
├── knowledge_base/
├── docs/
├── rag/
└── README.md
```

---

# 🔄 AI Workflow

```
Employee

↓

Describe Issue

↓

Intent Detection

↓

Knowledge Search

↓

AI Diagnosis

↓

Troubleshooting

↓

Issue Resolved?
        │
        │
   YES ─────────► Close Conversation
        │
        │
        ▼
NO

↓

Create Ticket

↓

Assign Team

↓

Approval (If Required)

↓

Resolve Issue

↓

Close Ticket
```

---

# 🔐 Security

- JWT Authentication
- Role Based Access Control
- Secure Environment Variables
- API Authentication
- Nginx Reverse Proxy
- CORS Protection
- Production Docker Deployment

---

# 📊 Supported Roles

| Role | Access |
|-------|--------|
| Employee | IT Support, Tickets, Actions |
| Manager | Approvals, Team Requests |
| Administrator | Full System Access |

---

# 📸 Screenshots

## Login

<h2 align="center">Login</h2>

<p align="center">
<img src="image.png" width="95%">
</p>

---

## 🏠 Dashboard

<h2 align="center">Dashboard</h2>

<p align="center">
<img src="image-2.png" width="95%">
</p>

---

## AI IT Support

<h2 align="center">AI IT Support</h2>

<p align="center">
<img src="image-1.png" width="95%">
</p>

---

## Manager Portal

<h2 align="center">Manager Portal</h2>

<p align="center">
<img src="image-3.png" width="95%">
</p>

---

## Administrator Dashboard

<h2 align="center">Administrator Dashboard</h2>

<p align="center">
<img src="image-4.png" width="95%">
</p>

---

## Analytics

<h2 align="center">Analytics</h2>

<p align="center">
<img src="image-5.png" width="95%">
</p>

---

# 🚀 Running Locally

## Backend

```bash
cd backend

python -m venv venv

pip install -r requirements.txt

uvicorn app.main:app --reload
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

---

# 🐳 Docker Deployment

```bash
docker compose -f infrastructure/compose/docker-compose.prod.yml build

docker compose -f infrastructure/compose/docker-compose.prod.yml up -d
```

---

# 📈 Monitoring

- Prometheus
- Grafana
- Health Checks
- Container Monitoring
- API Monitoring

---

# 🌟 Future Improvements

- Microsoft Teams Integration
- Email Automation
- Voice Assistant
- Multi-language Support
- Predictive Incident Detection
- AI Copilot Dashboard
- Agentic AI Workflows
- Enterprise SSO

---

# 👨‍💻 Author

**Raghvendra Bhati**

B.Tech CSE (Data Science)

AI Engineer | Machine Learning | Generative AI | Agentic AI

GitHub:
https://github.com/raghvendrabhati02

LinkedIn:
https://linkedin.com/in/raghvendrabhati0217

---

# 📄 License

This project was developed for educational and enterprise demonstration purposes.

© 2026 Raghvendra Bhati. All rights reserved.