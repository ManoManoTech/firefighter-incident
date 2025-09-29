# FireFighter - Architecture Overview

## 🔥 Project Description

**FireFighter** is **ManoMano**'s internal Incident Management Tool. It's a Django platform that automates and facilitates incident management by automatically creating Slack channels for communication and much more.

## 🏢 Repository Structure

**Two distinct repositories**:

1. **`impact/`** (GitLab - Private ManoMano)
   - 📂 Custom project for ManoMano
   - 🔧 Specific configurations, deployments, customizations
   - 🔐 Contains secrets and environment configurations
   - 📍 Location: `/Users/nicolas.lafitte/workspace/impact/`

2. **`firefighter-oss/`** (GitHub - Open Source)
   - 🌍 Open source version of the codebase
   - 📦 Application core, modules, tests
   - 🔗 Git submodule in the `impact/` project
   - 📍 Location: `/Users/nicolas.lafitte/workspace/impact/firefighter-oss/`
   - 🔗 GitHub: `ManoManoTech/firefighter-incident`

**Hybrid architecture**:

```text
impact/ (GitLab - Private)
├── firefighter-oss/ (Git submodule → GitHub Open Source)
│   ├── src/firefighter/        # Main source code
│   ├── tests/                  # Unit tests
│   ├── docs/                   # Documentation
│   └── pyproject.toml         # Package configuration
├── deploy/                     # ManoMano deployment scripts
├── config/                     # Environment configuration
└── secrets/                    # Sensitive environment variables
```

This approach allows ManoMano to:

- 🎁 **Contribute to open source** with the main codebase
- 🔒 **Keep private** specific configurations and secrets
- 🔄 **Easily synchronize** improvements between both repositories

## 🏗️ Main Architecture

**Key Technologies**:

- **Backend**: Django 4.2 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis + Celery
- **Frontend**: Django templates + HTMX
- **Integrations**: Slack Bot, JIRA, PagerDuty, Confluence
- **Monitoring**: Datadog (ddtrace)

**Main Modules**:

```text
src/firefighter/
├── incidents/          # 📋 Incident management (models, views, business logic)
├── slack/              # 💬 Slack integration (bot, events, notifications)
├── raid/               # 🎫 RAID module - JIRA ticket management for incidents
├── jira_app/           # 🔗 JIRA client and synchronization
├── pagerduty/          # 📟 PagerDuty integration for on-call
├── confluence/         # 📚 Post-mortem and documentation management
├── api/                # 🌐 REST API for external integrations
├── firefighter/        # ⚙️ Django configuration and utilities
└── components/         # 🧩 Reusable UI components
```

## 🚀 Key Features

### Incident Management

- **Automatic creation** of dedicated Slack channels per incident
- **Classification** by priority, severity, business impact
- **Time tracking** with milestones and costs
- **Role assignment** (Incident Commander, Communications Lead, etc.)
- **Automatic updates** with complete history

### Integrations

- **Slack**: Interactive bot, slash commands, modals
- **JIRA**: Automatic ticket creation via RAID module
- **PagerDuty**: Automatic on-call triggering
- **Confluence**: Post-mortem generation

### RAID Module (Recent Feature)

- **Intelligent routing** of JIRA tickets by team
- **Business impact validation** and priorities
- **Automatic attachment management**
- **Custom workflows** per project

## 🆕 Recently Added Features

### Component → IncidentCategory Migration

- **Major refactoring**: Renaming "Component" to "IncidentCategory"
- **Updates** to all models, views, templates
- **Database migration** for terminological consistency

### Slack Improvements

- **Error handling** for private messages (`messages_tab_disabled`)
- **New commands** and bot interactions
- **Optimization** of notifications and reminders

### Bidirectional Synchronization System

- **Impact ↔ JIRA sync**: Status, priority, assignee, title, description
- **Loop prevention**: Cache-based mechanism to prevent infinite sync loops
- **Field mapping**: Comprehensive mapping between Impact and JIRA field types
- **Error handling**: Graceful handling of sync failures with detailed logging

## 🧪 Testing Architecture

### Test Configuration

- **Test database**: PostgreSQL (`POSTGRES_DB=ff_dev`)
- **Environment variables**: Complete test isolation with FF_SLACK_SKIP_CHECKS
- **Coverage tracking**: pytest-cov with HTML reporting
- **Parallelized execution**: pytest-randomly for test order randomization

### Test Structure

```text
tests/
├── test_incidents/     # Incident management tests
├── test_slack/         # Slack integration tests
├── test_raid/          # RAID module tests
├── test_jira_app/      # JIRA client tests
├── test_api/           # API endpoint tests
└── test_firefighter/   # Core utilities tests
```

## 🎯 Current Objectives

- **Improve test coverage** to reach 60%+
- **Strengthen robustness** of external integrations
- **Optimize performance** of Celery tasks
- **Document architecture** to facilitate contribution