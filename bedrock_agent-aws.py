#!/usr/bin/env python3
"""
AWS Bedrock PKI Agent - Real-Time Interactive System

This agent provides two modes:
1. Demo Run: Automated PKI workflow demonstration with example data
2. Interactive Chat: Real-time Q&A about cryptography and PKI concepts

Uses .env file for AWS credentials - no need for aws configure!
"""

import boto3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import sys
import os
from pathlib import Path

# Try to import python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("⚠️  Warning: python-dotenv not installed. Install it with: pip install python-dotenv")

# ============================================================================
# CONFIGURATION - Load from .env file
# ============================================================================

def load_aws_config():
    """Load AWS configuration from .env file or environment variables."""
    
    # Load .env file if available
    if DOTENV_AVAILABLE:
        env_path = Path('.') / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            print("✅ Loaded configuration from .env file")
        else:
            print("⚠️  .env file not found. Create one using .env.example as a template")
    
    # Get configuration from environment variables
    config = {
        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'aws_region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
        'aws_output_format': os.getenv('AWS_OUTPUT_FORMAT', 'json')
    }
    
    # Validate required credentials
    if not config['aws_access_key_id'] or not config['aws_secret_access_key']:
        print("\n❌ AWS credentials not found!")
        print("\nPlease create a .env file with your AWS credentials:")
        print("1. Copy .env.example to .env")
        print("2. Fill in your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        print("\nOr set environment variables:")
        print("  export AWS_ACCESS_KEY_ID='your-key'")
        print("  export AWS_SECRET_ACCESS_KEY='your-secret'")
        sys.exit(1)
    
    return config


# ============================================================================
# PKI DEMO DATA & AGENTS (Same as before, but simplified)
# ============================================================================

class PolicyAgent:
    """Validates requests against security policies."""
    
    def __init__(self):
        self.policy = {
            "version": "2.3",
            "algorithms": {
                "RSA": {"allowed": True, "min_key_size": 3072, "max_key_size": 8192},
                "ECC": {"allowed": True, "allowed_curves": ["P-256", "P-384", "P-521"]},
                "DSA": {"allowed": False, "reason": "Deprecated - use RSA or ECC"}
            },
            "certificates": {"max_validity_days": 397, "min_validity_days": 1}
        }
    
    def validate(self, algorithm: str, key_size: int, validity_days: int) -> Dict:
        """Validate request against policy."""
        if algorithm not in self.policy['algorithms']:
            return {"approved": False, "reason": f"Algorithm {algorithm} not recognized"}
        
        algo_policy = self.policy['algorithms'][algorithm]
        if not algo_policy.get('allowed'):
            return {"approved": False, "reason": f"Algorithm {algorithm} not allowed: {algo_policy.get('reason')}"}
        
        if algorithm == "RSA" and key_size < algo_policy['min_key_size']:
            return {"approved": False, "reason": f"Key size {key_size} below minimum {algo_policy['min_key_size']}"}
        
        if validity_days > self.policy['certificates']['max_validity_days']:
            return {"approved": False, "reason": f"Validity {validity_days} exceeds maximum {self.policy['certificates']['max_validity_days']}"}
        
        return {"approved": True, "reason": f"Approved under policy v{self.policy['version']}"}


class SimplePKIManager:
    """Simplified PKI manager for demo purposes."""
    
    def __init__(self):
        self.policy_agent = PolicyAgent()
        self.certificates = []
        self.audit_log = []
    
    def issue_certificate(self, subject: str, algorithm: str = "RSA", 
                          key_size: int = 4096, validity_days: int = 90) -> Dict:
        """Issue a certificate with policy validation."""
        
        # Policy check
        policy_result = self.policy_agent.validate(algorithm, key_size, validity_days)
        
        self.log_event("POLICY_CHECK", {
            "approved": policy_result['approved'],
            "reason": policy_result['reason']
        })
        
        if not policy_result['approved']:
            return {"success": False, "error": f"Policy violation: {policy_result['reason']}"}
        
        # Simulate certificate issuance
        cert_id = f"cert-{len(self.certificates) + 1}"
        serial = f"DEMO-{len(self.certificates) + 1:04d}"
        not_before = datetime.now()
        not_after = not_before + timedelta(days=validity_days)
        
        cert = {
            "cert_id": cert_id,
            "subject": subject,
            "serial_number": serial,
            "algorithm": algorithm,
            "key_size": key_size,
            "not_before": not_before.isoformat(),
            "not_after": not_after.isoformat(),
            "status": "active"
        }
        
        self.certificates.append(cert)
        self.log_event("CERTIFICATE_ISSUED", {"cert_id": cert_id, "subject": subject})
        
        return {
            "success": True,
            "cert_id": cert_id,
            "serial_number": serial,
            "not_after": not_after.isoformat()
        }
    
    def list_certificates(self) -> List[Dict]:
        """List all certificates."""
        return self.certificates
    
    def log_event(self, event_type: str, details: Dict):
        """Log audit event."""
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        })


# ============================================================================
# AWS BEDROCK CLIENT
# ============================================================================

class BedrockAgent:
    """
    AWS Bedrock client for Claude interactions.
    Uses credentials from .env file.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize Bedrock client with credentials from .env.
        
        Args:
            config: Dictionary with AWS credentials and region
        """
        try:
            # Create boto3 session with explicit credentials
            session = boto3.Session(
                aws_access_key_id=config['aws_access_key_id'],
                aws_secret_access_key=config['aws_secret_access_key'],
                region_name=config['aws_region']
            )
            
            self.bedrock = session.client('bedrock-runtime')
            self.model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
            self.region = config['aws_region']
            
            print(f"✅ Connected to AWS Bedrock in {self.region}")
            
        except Exception as e:
            print(f"❌ Failed to connect to AWS Bedrock: {e}")
            print("\nMake sure you have:")
            print("1. Valid AWS credentials in .env file")
            print("2. Bedrock access enabled in your AWS account")
            print("3. Model access granted for Claude 3.5 Sonnet")
            sys.exit(1)
    
    def chat(self, message: str, system_prompt: str = None) -> str:
        """
        Send a message to Claude via Bedrock.
        
        Args:
            message: User message
            system_prompt: Optional system prompt for context
            
        Returns:
            Claude's response
        """
        try:
            # Prepare request
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            }
            
            # Add system prompt if provided
            if system_prompt:
                request_body["system"] = system_prompt
            
            # Call Bedrock
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            # Extract text from response
            if 'content' in response_body and len(response_body['content']) > 0:
                return response_body['content'][0]['text']
            else:
                return "Sorry, I couldn't generate a response."
                
        except Exception as e:
            return f"Error calling Bedrock: {str(e)}"


# ============================================================================
# DEMO MODE
# ============================================================================

class DemoMode:
    """
    Automated demo of PKI operations using Bedrock.
    No user input required - runs on example data.
    """
    
    def __init__(self, bedrock_agent: BedrockAgent):
        self.bedrock = bedrock_agent
        self.pki = SimplePKIManager()
    
    def run(self):
        """Run the complete demo workflow."""
        print("\n" + "="*70)
        print("🚀 PKI AGENT DEMO MODE - Automated Workflow")
        print("="*70 + "\n")
        
        # Demo scenarios
        scenarios = [
            {
                "name": "Valid Certificate Request",
                "request": "Issue a TLS certificate for api.example.com with RSA 4096, 90 days",
                "params": {"subject": "CN=api.example.com", "algorithm": "RSA", "key_size": 4096, "validity_days": 90}
            },
            {
                "name": "Policy Violation - Weak Key",
                "request": "Issue a certificate for old.example.com with RSA 2048",
                "params": {"subject": "CN=old.example.com", "algorithm": "RSA", "key_size": 2048, "validity_days": 90}
            },
            {
                "name": "Policy Violation - Validity Too Long",
                "request": "Issue a certificate for longterm.example.com valid for 500 days",
                "params": {"subject": "CN=longterm.example.com", "algorithm": "RSA", "key_size": 4096, "validity_days": 500}
            },
            {
                "name": "Valid ECC Certificate",
                "request": "Issue an ECC certificate for secure.example.com",
                "params": {"subject": "CN=secure.example.com", "algorithm": "ECC", "key_size": 256, "validity_days": 90}
            }
        ]
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n📋 Scenario {i}: {scenario['name']}")
            print(f"Request: {scenario['request']}")
            print("-" * 70)
            
            # Step 1: Use Bedrock to parse the request
            print("\n🤖 Using AWS Bedrock (Claude) to parse request...")
            
            parse_prompt = f"""Parse this PKI certificate request and confirm the parameters:

Request: "{scenario['request']}"

Expected parameters:
- Subject: {scenario['params']['subject']}
- Algorithm: {scenario['params']['algorithm']}
- Key Size: {scenario['params']['key_size']}
- Validity Days: {scenario['params']['validity_days']}

Respond with a brief confirmation of what certificate will be issued."""
            
            bedrock_response = self.bedrock.chat(parse_prompt)
            print(f"\n💬 Claude says: {bedrock_response}")
            
            # Step 2: Execute with PKI manager
            print("\n⚙️  Executing PKI workflow...")
            result = self.pki.issue_certificate(**scenario['params'])
            
            # Step 3: Display result
            time.sleep(1)  # Pause for readability
            
            if result['success']:
                print(f"\n✅ SUCCESS: Certificate issued")
                print(f"   • Certificate ID: {result['cert_id']}")
                print(f"   • Serial Number: {result['serial_number']}")
                print(f"   • Expires: {result['not_after']}")
            else:
                print(f"\n❌ REJECTED: {result['error']}")
            
            if i < len(scenarios):
                input("\nPress Enter to continue to next scenario...")
        
        # Summary
        print("\n" + "="*70)
        print("📊 DEMO SUMMARY")
        print("="*70)
        
        print(f"\n✅ Certificates Issued: {len(self.pki.list_certificates())}")
        
        print("\n📜 Certificate Inventory:")
        for cert in self.pki.list_certificates():
            print(f"   • {cert['cert_id']}: {cert['subject']} ({cert['status']})")
        
        print(f"\n📝 Audit Events: {len(self.pki.audit_log)}")
        for event in self.pki.audit_log[-5:]:  # Last 5 events
            print(f"   • {event['event_type']}: {event['details']}")
        
        print("\n" + "="*70)
        print("✨ Demo Complete!")
        print("="*70 + "\n")


# ============================================================================
# INTERACTIVE CHAT MODE
# ============================================================================

class InteractiveChatMode:
    """
    Real-time interactive chat with Claude via Bedrock.
    Answers questions about cryptography, PKI, and general topics.
    """
    
    def __init__(self, bedrock_agent: BedrockAgent):
        self.bedrock = bedrock_agent
        self.pki = SimplePKIManager()
        
        # System prompt for context
        self.system_prompt = """You are a helpful AI assistant with expertise in:
- Public Key Infrastructure (PKI)
- Cryptography (RSA, ECC, symmetric/asymmetric encryption)
- Certificate management and lifecycle
- Security best practices
- General technical topics

You can also execute PKI operations when asked. When the user requests certificate operations, 
acknowledge their request and explain what you would do, but remind them this is a demo system.

Be friendly, clear, and educational in your responses. Use examples when helpful.
"""
    
    def run(self):
        """Run interactive chat mode."""
        print("\n" + "="*70)
        print("💬 INTERACTIVE CHAT MODE - Ask Me Anything!")
        print("="*70)
        print("\nYou can ask about:")
        print("  • Cryptography concepts (RSA, ECC, AES, etc.)")
        print("  • PKI and certificate management")
        print("  • Security best practices")
        print("  • General technical topics")
        print("  • Or request certificate operations")
        print("\nType 'exit' or 'quit' to return to main menu")
        print("="*70 + "\n")
        
        conversation_history = []
        
        while True:
            # Get user input
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nExiting chat...")
                break
            
            # Check for exit
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\nReturning to main menu...\n")
                break
            
            if not user_input:
                continue
            
            # Check if user is requesting a certificate operation
            cert_keywords = ['issue', 'create', 'generate', 'certificate', 'cert']
            is_cert_request = any(keyword in user_input.lower() for keyword in cert_keywords)
            
            if is_cert_request:
                # Handle as PKI operation
                print("\n🤖 Processing PKI request with Bedrock...\n")
                
                # Ask Bedrock to extract parameters
                extract_prompt = f"""The user requested: "{user_input}"

This seems to be a PKI certificate request. Extract the following parameters (use defaults if not specified):
- Subject/Domain (default: example.com)
- Algorithm (default: RSA)
- Key Size (default: 4096 for RSA, 256 for ECC)
- Validity Days (default: 90)

Respond in JSON format only:
{{"subject": "CN=...", "algorithm": "...", "key_size": ..., "validity_days": ...}}"""
                
                params_response = self.bedrock.chat(extract_prompt)
                
                try:
                    # Try to parse JSON from response
                    params_str = params_response.strip()
                    if params_str.startswith("```"):
                        params_str = params_str.split("\n", 1)[1].rsplit("\n", 1)[0]
                    if params_str.startswith("json"):
                        params_str = params_str[4:].strip()
                    
                    params = json.loads(params_str)
                    
                    print(f"📋 Extracted parameters: {json.dumps(params, indent=2)}\n")
                    
                    # Execute PKI operation
                    result = self.pki.issue_certificate(
                        subject=params.get('subject', 'CN=example.com'),
                        algorithm=params.get('algorithm', 'RSA'),
                        key_size=params.get('key_size', 4096),
                        validity_days=params.get('validity_days', 90)
                    )
                    
                    if result['success']:
                        response = f"""✅ Certificate issued successfully!

Certificate ID: {result['cert_id']}
Serial Number: {result['serial_number']}
Expires: {result['not_after']}

The certificate has been added to the inventory. You can list all certificates by asking "list certificates"."""
                    else:
                        response = f"❌ Certificate issuance failed: {result['error']}"
                    
                except json.JSONDecodeError:
                    # Fall back to normal chat
                    response = self.bedrock.chat(user_input, self.system_prompt)
            
            elif 'list' in user_input.lower() and 'cert' in user_input.lower():
                # List certificates
                certs = self.pki.list_certificates()
                if certs:
                    response = f"📜 Certificate Inventory ({len(certs)} certificates):\n\n"
                    for cert in certs:
                        response += f"• {cert['cert_id']}: {cert['subject']}\n"
                        response += f"  Serial: {cert['serial_number']}, Expires: {cert['not_after']}\n\n"
                else:
                    response = "No certificates in inventory yet. Try issuing one!"
            
            else:
                # Normal chat
                print("\n🤖 Asking Claude via Bedrock...\n")
                response = self.bedrock.chat(user_input, self.system_prompt)
            
            # Display response
            print(f"Claude: {response}\n")
            
            # Add to conversation history
            conversation_history.append({
                "user": user_input,
                "assistant": response,
                "timestamp": datetime.now().isoformat()
            })


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def print_banner():
    """Print application banner."""
    print("\n" + "="*70)
    print("  🔐 AWS Bedrock PKI Agent - Real-Time Interactive System")
    print("="*70)
    print("\n  Powered by AWS Bedrock + Claude 3.5 Sonnet")
    print("  Uses .env file for AWS credentials - no aws configure needed!\n")
    print("="*70 + "\n")


def main():
    """Main application entry point."""
    print_banner()
    
    # Load AWS configuration from .env
    print("🔍 Loading AWS configuration from .env file...")
    config = load_aws_config()
    print(f"   Region: {config['aws_region']}\n")
    
    # Initialize Bedrock agent
    try:
        bedrock_agent = BedrockAgent(config)
    except Exception as e:
        print(f"\n❌ Failed to initialize Bedrock agent: {e}")
        sys.exit(1)
    
    # Main loop
    while True:
        print("\n" + "="*70)
        print("  CHOOSE MODE")
        print("="*70)
        print("\n  1. 🎬 Demo Run - Automated PKI workflow demonstration")
        print("     (No input needed, runs on example data)")
        print("\n  2. 💬 Interactive Chat - Real-time Q&A with Claude")
        print("     (Ask about crypto, PKI, or anything else)")
        print("\n  3. 🚪 Exit")
        print("\n" + "="*70)
        
        try:
            choice = input("\nSelect mode (1/2/3): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting...")
            break
        
        if choice == '1':
            # Demo mode
            demo = DemoMode(bedrock_agent)
            demo.run()
        
        elif choice == '2':
            # Interactive chat
            chat = InteractiveChatMode(bedrock_agent)
            chat.run()
        
        elif choice == '3':
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("\n❌ Invalid choice. Please select 1, 2, or 3.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
        sys.exit(0)
