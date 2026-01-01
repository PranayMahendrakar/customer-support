#!/usr/bin/env python3
"""
Contextual Customer Support Bot - Llama-Based Support Assistant
Maintains context across interactions and provides personalized help
Author: Pranay M
"""

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt, Confirm
from rich.markdown import Markdown
import json
import sqlite3
from datetime import datetime
from typing import Optional
import hashlib

console = Console()

class CustomerDatabase:
    def __init__(self, db_path: str = "customers.db"):
        self.conn = sqlite3.connect(db_path)
        self._init_db()
    
    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                tier TEXT DEFAULT 'standard',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                message TEXT,
                response TEXT,
                sentiment TEXT,
                category TEXT,
                resolved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id TEXT,
                subject TEXT,
                description TEXT,
                priority TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                question TEXT,
                answer TEXT,
                keywords TEXT
            );
        """)
        self.conn.commit()
    
    def get_customer(self, customer_id: str) -> Optional[dict]:
        cursor = self.conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"id": row[0], "name": row[1], "email": row[2], "tier": row[3]}
        return None
    
    def create_customer(self, name: str, email: str, tier: str = "standard") -> str:
        customer_id = hashlib.md5(email.encode()).hexdigest()[:8]
        self.conn.execute(
            "INSERT OR REPLACE INTO customers (id, name, email, tier) VALUES (?, ?, ?, ?)",
            (customer_id, name, email, tier)
        )
        self.conn.commit()
        return customer_id
    
    def get_history(self, customer_id: str, limit: int = 10) -> list:
        cursor = self.conn.execute(
            """SELECT message, response, sentiment, category, created_at 
               FROM interactions WHERE customer_id = ? 
               ORDER BY created_at DESC LIMIT ?""",
            (customer_id, limit)
        )
        return [{"message": r[0], "response": r[1], "sentiment": r[2], 
                 "category": r[3], "timestamp": r[4]} for r in cursor.fetchall()]
    
    def save_interaction(self, customer_id: str, message: str, response: str, 
                        sentiment: str, category: str):
        self.conn.execute(
            """INSERT INTO interactions (customer_id, message, response, sentiment, category)
               VALUES (?, ?, ?, ?, ?)""",
            (customer_id, message, response, sentiment, category)
        )
        self.conn.commit()
    
    def create_ticket(self, customer_id: str, subject: str, description: str, 
                     priority: str) -> int:
        cursor = self.conn.execute(
            """INSERT INTO tickets (customer_id, subject, description, priority)
               VALUES (?, ?, ?, ?)""",
            (customer_id, subject, description, priority)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_tickets(self, customer_id: str) -> list:
        cursor = self.conn.execute(
            "SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,)
        )
        return [{"id": r[0], "subject": r[2], "description": r[3], 
                 "priority": r[4], "status": r[5]} for r in cursor.fetchall()]


class CustomerSupportBot:
    def __init__(self, model: str = "llama3.2"):
        self.model = model
        self.db = CustomerDatabase()
        self.current_customer = None
        self.conversation_context = []
        self.company_info = {
            "name": "TechCorp Solutions",
            "products": ["CloudSync Pro", "DataGuard", "AutomateX", "SecureVault"],
            "support_hours": "24/7",
            "escalation_email": "escalations@techcorp.com"
        }
    
    def set_customer(self, customer_id: str) -> bool:
        customer = self.db.get_customer(customer_id)
        if customer:
            self.current_customer = customer
            self.conversation_context = self.db.get_history(customer_id, 5)
            return True
        return False
    
    def register_customer(self, name: str, email: str, tier: str = "standard") -> str:
        customer_id = self.db.create_customer(name, email, tier)
        self.set_customer(customer_id)
        return customer_id
    
    def analyze_sentiment(self, message: str) -> dict:
        prompt = f"""Analyze the sentiment and urgency of this customer message.

Message: {message}

Return JSON:
{{
    "sentiment": "positive/neutral/negative/frustrated/angry",
    "urgency": "low/medium/high/critical",
    "emotion": "primary emotion detected",
    "escalation_needed": true/false,
    "key_concerns": ["list of concerns"]
}}"""

        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        return self._parse_json(response['message']['content'])
    
    def categorize_issue(self, message: str) -> dict:
        prompt = f"""Categorize this customer support issue.

Message: {message}

Categories: billing, technical, account, product, shipping, returns, general

Return JSON:
{{
    "primary_category": "main category",
    "secondary_category": "if applicable",
    "subcategory": "more specific",
    "product_mentioned": "product name if any",
    "keywords": ["relevant keywords"]
}}"""

        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        return self._parse_json(response['message']['content'])
    
    def generate_response(self, message: str) -> dict:
        # Get context
        history_text = "\n".join([
            f"Customer: {h['message']}\nAgent: {h['response']}" 
            for h in self.conversation_context[-3:]
        ])
        
        customer_info = ""
        if self.current_customer:
            customer_info = f"""
Customer: {self.current_customer['name']}
Tier: {self.current_customer['tier']}
"""
        
        prompt = f"""You are a friendly, helpful customer support agent for {self.company_info['name']}.

Company Products: {', '.join(self.company_info['products'])}
{customer_info}

Previous conversation:
{history_text}

Current message: {message}

Guidelines:
1. Be empathetic and professional
2. Acknowledge the customer's concern
3. Provide clear, actionable solutions
4. Offer alternatives when possible
5. Know when to escalate
6. Personalize based on customer history

Respond naturally and helpfully. If you need to create a ticket or escalate, indicate that."""

        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        response_text = response['message']['content']
        
        # Analyze and save
        sentiment = self.analyze_sentiment(message)
        category = self.categorize_issue(message)
        
        if self.current_customer:
            self.db.save_interaction(
                self.current_customer['id'],
                message, response_text,
                sentiment.get('sentiment', 'neutral'),
                category.get('primary_category', 'general')
            )
            self.conversation_context.append({
                "message": message,
                "response": response_text
            })
        
        return {
            "response": response_text,
            "sentiment": sentiment,
            "category": category,
            "escalation_recommended": sentiment.get('escalation_needed', False)
        }
    
    def suggest_solutions(self, issue: str) -> list:
        prompt = f"""Suggest solutions for this customer issue.

Issue: {issue}

Products: {', '.join(self.company_info['products'])}

Return JSON:
{{
    "solutions": [
        {{
            "solution": "solution description",
            "steps": ["step 1", "step 2"],
            "difficulty": "easy/medium/hard",
            "estimated_time": "time to resolve"
        }}
    ],
    "self_service_options": ["option 1"],
    "faq_references": ["relevant FAQ topics"],
    "escalation_path": "when to escalate"
}}"""

        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        result = self._parse_json(response['message']['content'])
        return result.get('solutions', [])
    
    def create_support_ticket(self, issue: str) -> dict:
        if not self.current_customer:
            return {"error": "No customer selected"}
        
        sentiment = self.analyze_sentiment(issue)
        category = self.categorize_issue(issue)
        
        priority_map = {"critical": "urgent", "high": "high", "medium": "normal", "low": "low"}
        priority = priority_map.get(sentiment.get('urgency', 'medium'), 'normal')
        
        ticket_id = self.db.create_ticket(
            self.current_customer['id'],
            category.get('primary_category', 'General Issue'),
            issue,
            priority
        )
        
        return {
            "ticket_id": ticket_id,
            "priority": priority,
            "category": category.get('primary_category'),
            "status": "open"
        }
    
    def get_customer_summary(self) -> dict:
        if not self.current_customer:
            return {"error": "No customer selected"}
        
        history = self.db.get_history(self.current_customer['id'], 20)
        tickets = self.db.get_tickets(self.current_customer['id'])
        
        sentiment_counts = {}
        category_counts = {}
        for h in history:
            s = h.get('sentiment', 'neutral')
            c = h.get('category', 'general')
            sentiment_counts[s] = sentiment_counts.get(s, 0) + 1
            category_counts[c] = category_counts.get(c, 0) + 1
        
        return {
            "customer": self.current_customer,
            "total_interactions": len(history),
            "open_tickets": len([t for t in tickets if t['status'] == 'open']),
            "sentiment_distribution": sentiment_counts,
            "common_issues": category_counts,
            "recent_tickets": tickets[:5]
        }
    
    def generate_followup(self, ticket_id: int) -> str:
        prompt = f"""Generate a professional follow-up message for ticket #{ticket_id}.

Customer: {self.current_customer['name'] if self.current_customer else 'Valued Customer'}

The ticket has been resolved. Create a follow-up that:
1. Thanks them for their patience
2. Summarizes the resolution
3. Offers additional help
4. Requests feedback

Keep it warm and professional."""

        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        return response['message']['content']
    
    def handle_escalation(self, issue: str, reason: str) -> dict:
        prompt = f"""Prepare an escalation brief for this issue.

Issue: {issue}
Escalation Reason: {reason}
Customer: {self.current_customer['name'] if self.current_customer else 'Unknown'}
Customer Tier: {self.current_customer['tier'] if self.current_customer else 'Standard'}

Create an escalation summary with:
1. Issue summary
2. Steps already taken
3. Why escalation is needed
4. Recommended next steps
5. Customer impact assessment"""

        response = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
        
        return {
            "escalation_brief": response['message']['content'],
            "escalation_to": self.company_info['escalation_email'],
            "priority": "high"
        }
    
    def _parse_json(self, content: str) -> dict:
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(content[start:end])
        except:
            pass
        return {"raw_response": content}


def display_menu():
    table = Table(title="💬 Customer Support Bot", show_header=True)
    table.add_column("Option", style="cyan", width=6)
    table.add_column("Feature", style="green")
    table.add_column("Description", style="white")
    
    table.add_row("1", "Chat", "Start support conversation")
    table.add_row("2", "Register Customer", "Add new customer")
    table.add_row("3", "Load Customer", "Load existing customer")
    table.add_row("4", "Customer Summary", "View customer profile")
    table.add_row("5", "Create Ticket", "Open support ticket")
    table.add_row("6", "View Tickets", "See customer tickets")
    table.add_row("7", "Suggest Solutions", "Get solution suggestions")
    table.add_row("8", "Escalate", "Prepare escalation")
    table.add_row("9", "Follow-up", "Generate follow-up message")
    table.add_row("0", "Exit", "Close application")
    
    console.print(table)


def main():
    console.print(Panel.fit(
        "[bold blue]💬 Contextual Customer Support Bot[/bold blue]\n"
        "[green]AI-Powered Personalized Support Assistant[/green]\n"
        "[dim]Author: Pranay M[/dim]",
        border_style="blue"
    ))
    
    bot = CustomerSupportBot()
    
    while True:
        display_menu()
        if bot.current_customer:
            console.print(f"[dim]Current customer: {bot.current_customer['name']} ({bot.current_customer['tier']})[/dim]")
        
        choice = Prompt.ask("\n[cyan]Select option[/cyan]", default="0")
        
        if choice == "0":
            console.print("[yellow]Goodbye! Thank you for using our support! 💬[/yellow]")
            break
        
        elif choice == "1":
            if not bot.current_customer:
                console.print("[yellow]Please register or load a customer first[/yellow]")
                continue
            
            console.print("[dim]Type 'exit' to end conversation[/dim]")
            while True:
                message = Prompt.ask("\n[cyan]Customer[/cyan]")
                if message.lower() == 'exit':
                    break
                
                with console.status("[bold green]Processing..."):
                    result = bot.generate_response(message)
                
                console.print(f"\n[green]Agent:[/green] {result['response']}")
                
                if result.get('escalation_recommended'):
                    console.print("[yellow]⚠️ Escalation may be needed[/yellow]")
        
        elif choice == "2":
            name = Prompt.ask("Customer name")
            email = Prompt.ask("Email")
            tier = Prompt.ask("Tier", choices=["standard", "premium", "enterprise"], default="standard")
            customer_id = bot.register_customer(name, email, tier)
            console.print(f"[green]✓ Customer registered: {customer_id}[/green]")
        
        elif choice == "3":
            customer_id = Prompt.ask("Customer ID")
            if bot.set_customer(customer_id):
                console.print(f"[green]✓ Loaded: {bot.current_customer['name']}[/green]")
            else:
                console.print("[red]Customer not found[/red]")
        
        elif choice == "4":
            summary = bot.get_customer_summary()
            if "error" in summary:
                console.print(f"[red]{summary['error']}[/red]")
            else:
                console.print(Panel(Markdown(f"```json\n{json.dumps(summary, indent=2)}\n```"),
                                   title="👤 Customer Summary"))
        
        elif choice == "5":
            issue = Prompt.ask("Describe the issue")
            with console.status("[bold green]Creating ticket..."):
                ticket = bot.create_support_ticket(issue)
            console.print(Panel(f"Ticket #{ticket['ticket_id']} created\nPriority: {ticket['priority']}",
                               title="🎫 Ticket Created", border_style="green"))
        
        elif choice == "6":
            if bot.current_customer:
                tickets = bot.db.get_tickets(bot.current_customer['id'])
                table = Table(title="🎫 Tickets")
                table.add_column("ID", style="cyan")
                table.add_column("Subject")
                table.add_column("Priority")
                table.add_column("Status")
                for t in tickets:
                    table.add_row(str(t['id']), t['subject'], t['priority'], t['status'])
                console.print(table)
            else:
                console.print("[yellow]Load a customer first[/yellow]")
        
        elif choice == "7":
            issue = Prompt.ask("Describe the issue")
            with console.status("[bold green]Finding solutions..."):
                solutions = bot.suggest_solutions(issue)
            console.print(Panel(Markdown(f"```json\n{json.dumps(solutions, indent=2)}\n```"),
                               title="💡 Suggested Solutions"))
        
        elif choice == "8":
            issue = Prompt.ask("Issue to escalate")
            reason = Prompt.ask("Escalation reason")
            with console.status("[bold green]Preparing escalation..."):
                escalation = bot.handle_escalation(issue, reason)
            console.print(Panel(escalation['escalation_brief'], title="⬆️ Escalation Brief"))
        
        elif choice == "9":
            ticket_id = IntPrompt.ask("Ticket ID")
            with console.status("[bold green]Generating follow-up..."):
                followup = bot.generate_followup(ticket_id)
            console.print(Panel(followup, title="📧 Follow-up Message"))
        
        console.print("\n" + "="*50)


if __name__ == "__main__":
    main()
