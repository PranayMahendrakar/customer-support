# 💬 Contextual Customer Support Bot

**AI-Powered Personalized Support Assistant**

Author: Pranay M

## Overview

A Llama-based customer support bot that maintains context across multiple interactions, provides personalized help based on customer history, and manages support tickets.

## Features

- **Contextual Conversations**: Remembers previous interactions
- **Sentiment Analysis**: Detects customer emotions and urgency
- **Issue Categorization**: Auto-categorizes support issues
- **Ticket Management**: Create and track support tickets
- **Solution Suggestions**: AI-powered troubleshooting
- **Customer Profiles**: Track customer tier and history
- **Escalation Handling**: Prepare escalation briefs
- **Follow-up Generation**: Create personalized follow-ups

## Installation

```bash
ollama pull llama3.2
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

## Example

```python
from main import CustomerSupportBot

bot = CustomerSupportBot()

# Register customer
customer_id = bot.register_customer("John Doe", "john@example.com", "premium")

# Start conversation
result = bot.generate_response("My CloudSync Pro isn't syncing files")
print(result['response'])
print(f"Sentiment: {result['sentiment']['sentiment']}")

# Create ticket
ticket = bot.create_support_ticket("Sync issues with CloudSync Pro")
```

## Database

Uses SQLite to persist:
- Customer profiles
- Interaction history
- Support tickets
- Knowledge base

## License

MIT License
