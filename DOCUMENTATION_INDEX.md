# Kassa Integration Service - Documentation Index

Welcome! This is your guide to all documentation for the **POS User Registration Button** feature and the broader Kassa Integration Service system.

## Quick Navigation

### 🎯 Getting Started

**New to the project?** Start here:

1. **[README.md](README.md)** (5 min read)
   - What is Kassa Integration Service?
   - Quick setup instructions
   - Architecture overview
   - Troubleshooting guide

2. **[DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md)** (10 min read)
   - 5-minute setup
   - Common tasks (add fields, validate, etc.)
   - Troubleshooting with examples
   - Quick reference table

### 📚 Complete Documentation

**Detailed references:**

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** (20 min read)
   - Complete system architecture
   - All components explained
   - Data flow diagrams
   - Technology stack
   - Scalability & performance
   - GDPR compliance
   - Future roadmap

2. **[POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md)** (15 min read)
   - Feature overview & benefits
   - User flow (happy path & offline)
   - Form fields & validation
   - RabbitMQ integration
   - Configuration options
   - Error handling
   - Testing plan

3. **[POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)** (25 min read)
   - Frontend API (JavaScript/OWL)
   - Backend API (Python/Odoo)
   - Message format (XML)
   - Error codes & solutions
   - Code examples (6 complete examples)
   - Integration points

4. **[DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md)** (20 min read)
   - Pre-deployment checks
   - Step-by-step deployment
   - Unit testing
   - Integration testing
   - End-to-end testing
   - Validation checklist
   - Rollback procedures
   - Performance tuning

### 🔧 By Role

**Choose based on your role:**

#### 👨‍💼 Project Manager
1. [README.md](README.md) - Project overview
2. [ARCHITECTURE.md](ARCHITECTURE.md) - Technical scope & components
3. [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) - Rollout plan

#### 👨‍💻 Backend Developer (Python/Odoo)
1. [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) - Common tasks
2. [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md) - Backend API
3. [src/models/user.py](../src/models/user.py) - User CRUD code
4. [src/messaging/user_consumer.py](../src/messaging/user_consumer.py) - Message handler

#### 👨‍💻 Frontend Developer (JavaScript/OWL)
1. [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) - Common tasks
2. [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md) - Frontend API
3. [kassa_pos/static/src/js/UserRegistration.js](../kassa_pos/static/src/js/UserRegistration.js) - Component code
4. [kassa_pos/views/user_registration_templates.xml](../kassa_pos/views/user_registration_templates.xml) - Templates

#### 🧪 QA/Tester
1. [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md) - Feature specification
2. [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) - Test plan
3. [src/tests/test_user_crud.py](../src/tests/test_user_crud.py) - Test examples
4. [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) - Manual testing

#### 🚀 DevOps/Infrastructure
1. [README.md](README.md) - Setup & infrastructure
2. [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) - Deployment steps
3. [docker-compose.production.yml](docker-compose.production.yml) - Production container config
4. [Dockerfile](../Dockerfile) - Build config

---

## Document Summary

| Document | Length | Audience | Purpose |
|----------|--------|----------|---------|
| [README.md](README.md) | 5 min | Everyone | Overview, setup, troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 20 min | Developers, Architects | System design, components, flows |
| [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md) | 15 min | Developers, QA, PM | Feature spec, user flows |
| [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md) | 25 min | Developers | API reference, code examples |
| [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) | 10 min | Developers | Common tasks, quick solutions |
| [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) | 20 min | QA, DevOps | Testing, deployment, rollback |
| This file | - | Everyone | Navigation & orientation |

---

## By Task

**Find documentation for your task:**

### Installing/Deploying
→ [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) (Deployment Steps section)

### Setting Up Development Environment  
→ [README.md](README.md) + [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md)

### Adding a New Field to Registration Form
→ [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) (Common Tasks section)

### Understanding System Architecture
→ [ARCHITECTURE.md](ARCHITECTURE.md)

### Testing the Feature
→ [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) (Testing Strategy section)

### Finding API Documentation
→ [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)

### Debugging an Issue
→ [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) (Troubleshooting Guide section)

### Understanding the User Registration Flow
→ [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md) (User Flow section)

### Implementing an Enhancement
→ [ARCHITECTURE.md](ARCHITECTURE.md) (Future Enhancements section) +
[DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) (Common Tasks section)

### Learning Message Format
→ [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md) (Message Format section)

### Rolling Back a Bad Deployment
→ [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) (Rollback Procedures section)

---

## Key Concepts Glossary

### POS User Registration Button
The **feature** that allows Odoo POS terminals to manually register new users when scanners fail.

- **Related docs:** [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md), [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md)

### User CRUD System
The **core backend system** for creating, reading, updating, and deleting users in the Integration Service.

- **Related docs:** [ARCHITECTURE.md](ARCHITECTURE.md), [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)

### Integration Service
The **middle layer** that receives user data from POS and syncs it to the CRM via RabbitMQ.

- **Related docs:** [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md)

### UserStore
The **in-memory database** that stores all registered users with O(1) lookup by ID or badge.

- **Related docs:** [ARCHITECTURE.md](ARCHITECTURE.md) (Component section), [src/models/user.py](../src/models/user.py)

### UserConsumer
The **message handler** that processes incoming User messages from RabbitMQ.

- **Related docs:** [ARCHITECTURE.md](ARCHITECTURE.md), [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)

### Message Queue (user.message.queue)
The **fallback queue** in Odoo that stores pending user messages when RabbitMQ is offline.

- **Related docs:** [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md#fallback-queue), [ARCHITECTURE.md](ARCHITECTURE.md) (Scenario 2)

---

## Workflows by Scenario

### Scenario: "I found a bug in the registration form"

1. **Identify the issue**
   - Check browser console (F12)
   - Check Odoo server logs
   - See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#troubleshooting-guide)

2. **Find related code**
   - Frontend: [kassa_pos/static/src/js/UserRegistration.js](../kassa_pos/static/src/js/UserRegistration.js)
   - Backend: [kassa_pos/models/user_registration.py](../kassa_pos/models/user_registration.py)

3. **Fix & test**
   - Follow steps in [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#common-tasks)
   - Run tests: `python -m pytest src/tests/test_user_crud.py -v`

4. **Deploy**
   - Follow [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) steps

### Scenario: "I need to add a new field to the form"

1. **Understand the flow**
   - Read [ARCHITECTURE.md](ARCHITECTURE.md#component-deep-dives) (Component section)

2. **Make changes**
   - Follow [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#add-a-new-field-to-registration-form)

3. **Test thoroughly**
   - See [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md#functional-tests)

4. **Deploy**
   - Follow [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) steps

### Scenario: "RabbitMQ is offline, what happens?"

1. **Understand fallback behavior**
   - Read [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md#fallback-path)
   - Read [ARCHITECTURE.md](ARCHITECTURE.md#scenario-2-offline-network-failure)

2. **Verify messages are queued**
   - See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#debug-rabbitmq-queue)

3. **Restart RabbitMQ and retry**
   - See [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md#offline-testing)

---

## Code References

### Frontend Code

- **Main Component:** [kassa_pos/static/src/js/UserRegistration.js](../kassa_pos/static/src/js/UserRegistration.js)
  - Class: `UserRegistrationModal`
  - See: [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md#frontend-api)

- **Templates:** [kassa_pos/views/user_registration_templates.xml](../kassa_pos/views/user_registration_templates.xml)
  - Components: Modal form, buttons
  - See: [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md#add-user-button)

### Backend Code

- **Handler:** [kassa_pos/models/user_registration.py](../kassa_pos/models/user_registration.py)
  - Class: `PosSession` (extended), `UserMessageQueue`
  - See: [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md#backend-api)

- **User Model:** [src/models/user.py](../src/models/user.py)
  - Class: `User`, `UserStore`
  - See: [ARCHITECTURE.md](ARCHITECTURE.md#component-deep-dives) (Section 3)

- **Message Consumer:** [src/messaging/user_consumer.py](../src/messaging/user_consumer.py)
  - Class: `UserConsumer`
  - See: [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md#backend-api) (UserConsumer section)

### Tests

- **Unit Tests:** [src/tests/test_user_crud.py](../src/tests/test_user_crud.py)
  - 40+ test cases
  - See: [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md#unit-tests)

---

## Frequently Asked Questions

### Q: How do I enable the feature?

**A:** See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#5-minute-setup) (Enable the Feature section)

### Q: What happens when RabbitMQ is offline?

**A:** See [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md#fallback-path) or [ARCHITECTURE.md](ARCHITECTURE.md#scenario-2-offline-network-failure)

### Q: How do I add a new field?

**A:** See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#add-a-new-field-to-registration-form)

### Q: How do I deploy to production?

**A:** See [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md#deployment-steps)

### Q: How do I run tests?

**A:** See [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md#unit-tests)

### Q: What's the complete API reference?

**A:** See [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)

### Q: What should I do if there's an error?

**A:** See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#troubleshooting-guide)

---

## Document Maintenance

**Last Updated:** March 29, 2026  
**Documentation Version:** 1.0  
**Status:** Complete

### How to Keep Docs Updated

1. **When adding a feature:** Update [ARCHITECTURE.md](ARCHITECTURE.md) and relevant specific docs
2. **When fixing a bug:** Document the solution in [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) troubleshooting
3. **When deploying:** Update version numbers and dates
4. **When changing APIs:** Update [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)

---

## Getting Help

### For Development Questions
→ See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md#need-help) or [ARCHITECTURE.md](ARCHITECTURE.md)

### For Testing/QA Questions
→ See [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md)

### For Deployment Questions
→ See [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md#deployment-steps)

### For API/Integration Questions
→ See [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md)

### For Architecture/Design Questions
→ See [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Quick Links

**All documentation files:**

1. [README.md](README.md) - Start here
2. [ARCHITECTURE.md](ARCHITECTURE.md) - System design
3. [POS_USER_REGISTRATION.md](POS_USER_REGISTRATION.md) - Feature spec
4. [POS_USER_REGISTRATION_API.md](POS_USER_REGISTRATION_API.md) - API reference
5. [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md) - Quick solutions
6. [DEPLOYMENT_TESTING_GUIDE.md](DEPLOYMENT_TESTING_GUIDE.md) - Deploy & test
7. [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - This file

**Key code files:**

1. [src/models/user.py](../src/models/user.py) - User CRUD
2. [src/messaging/user_consumer.py](../src/messaging/user_consumer.py) - Message handler
3. [kassa_pos/models/user_registration.py](../kassa_pos/models/user_registration.py) - POS backend
4. [kassa_pos/static/src/js/UserRegistration.js](../kassa_pos/static/src/js/UserRegistration.js) - POS frontend
5. [src/tests/test_user_crud.py](../src/tests/test_user_crud.py) - Tests

---

**Questions? Check the relevant doc above, or contact the development team.**

🎯 **Pro Tip:** Use this index as a bookmark. Come back here when you need to find something!
