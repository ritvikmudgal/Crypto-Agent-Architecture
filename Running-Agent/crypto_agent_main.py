"""
Cryptographic Agent using AWS Bedrock with MCP Plugin Architecture
This agent orchestrates cryptographic operations without performing crypto math directly.
"""

import os
import json
#from dotenv import load_dotenv
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys

# Load environment variables
#load_dotenv()

class CryptoAgentConfig:
    """Configuration management for the crypto agent"""
    def __init__(self):
        self.aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.getenv('AWS_REGION', 'us-east-1')
        self.bedrock_model_id = os.getenv('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0')
        
        # Validate required configs
        # if not all([self.aws_access_key, self.aws_secret_key]):
        #     raise ValueError("AWS credentials not found in .env file")

class MCPPluginManager:
    """Manages MCP plugins for cryptographic operations"""
    def __init__(self):
        self.plugins = {}
        self._load_plugins()
    
    def _load_plugins(self):
        """Load all available MCP plugins"""
        try:
            from plugins.crypto_plugin import CryptoMCPPlugin
            from plugins.pki_plugin import PKIMCPPlugin
            from plugins.policy_plugin import PolicyMCPPlugin
            
            self.plugins['crypto'] = CryptoMCPPlugin()
            self.plugins['pki'] = PKIMCPPlugin()
            self.plugins['policy'] = PolicyMCPPlugin()
            
            print(f"✓ Loaded {len(self.plugins)} MCP plugins successfully")
        except ImportError as e:
            print(f"⚠ Warning: Some plugins failed to load: {e}")
    
    def get_tools_schema(self) -> List[Dict]:
        """Get combined tool schemas from all plugins"""
        tools = []
        for plugin_name, plugin in self.plugins.items():
            tools.extend(plugin.get_tools())
        return tools
    
    def execute_tool(self, tool_name: str, parameters: Dict) -> Any:
        """Execute a tool from any loaded plugin"""
        for plugin in self.plugins.values():
            if hasattr(plugin, tool_name):
                method = getattr(plugin, tool_name)
                return method(**parameters)
        raise ValueError(f"Tool '{tool_name}' not found in any plugin")

class BedrockCryptoAgent:
    """Main agent class using AWS Bedrock with Claude"""
    def __init__(self, config: CryptoAgentConfig):
        self.config = config
        self.plugin_manager = MCPPluginManager()
        self.conversation_history = []
        
        import boto3

        self.bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name="us-east-1"
        )

        
        print(f"✓ Connected to AWS Bedrock in region: {self.config.aws_region}")
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt for Claude with cryptographic context"""
        return """You are a specialized Cryptographic Operations Agent with expertise in PKI and asymmetric cryptography.

CORE RESPONSIBILITIES:
- Orchestrate cryptographic operations using available MCP tools
- NEVER perform cryptographic mathematics directly
- Always use approved tools for key generation, CSR creation, certificate operations
- Enforce cryptographic policies and best practices
- Provide audit trails for all operations

AVAILABLE TOOLS:
You have access to MCP plugins that provide cryptographic capabilities:
- Crypto Plugin: Key pair generation, CSR creation/validation
- PKI Plugin: Certificate operations, CA interactions
- Policy Plugin: Policy validation, compliance checking

STRICT RULES:
1. NEVER generate keys manually - always use the generate_key_pair tool
2. NEVER perform cryptographic calculations - delegate to tools
3. ALWAYS validate policies before executing operations
4. ALWAYS log operations for audit purposes
5. Reject requests that violate cryptographic best practices

When a user requests a cryptographic operation:
1. Plan the steps required
2. Validate against policies
3. Execute using appropriate tools
4. Return results with audit information

Be helpful but security-conscious. Explain your reasoning."""

    def _invoke_bedrock(self, user_message: str, include_tools: bool = True) -> Dict:
        """Invoke AWS Bedrock with Claude model"""
        messages = self.conversation_history + [
            {"role": "user", "content": user_message}
        ]
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": self._build_system_prompt(),
            "messages": messages
        }
        
        # Add tools if requested
        if include_tools:
            request_body["tools"] = self.plugin_manager.get_tools_schema()
        
        response = self.bedrock_client.invoke_model(
            modelId=self.config.bedrock_model_id,
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body
    
    def _handle_tool_use(self, response_body: Dict) -> Optional[str]:
        """Handle tool use blocks from Claude's response"""
        if response_body.get('stop_reason') != 'tool_use':
            return None
        
        tool_results = []
        
        for content_block in response_body.get('content', []):
            if content_block.get('type') == 'tool_use':
                tool_name = content_block.get('name')
                tool_input = content_block.get('input', {})
                tool_use_id = content_block.get('id')
                
                print(f"\n🔧 Executing tool: {tool_name}")
                print(f"   Parameters: {json.dumps(tool_input, indent=2)}")
                
                try:
                    result = self.plugin_manager.execute_tool(tool_name, tool_input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result)
                    })
                    print(f"✓ Tool executed successfully")
                except Exception as e:
                    error_msg = f"Tool execution failed: {str(e)}"
                    print(f"✗ {error_msg}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps({"error": error_msg}),
                        "is_error": True
                    })
        
        if tool_results:
            # Continue conversation with tool results
            self.conversation_history.append({
                "role": "assistant",
                "content": response_body.get('content', [])
            })
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            
            # Get Claude's final response
            final_response = self._invoke_bedrock("", include_tools=True)
            return self._extract_text_response(final_response)
        
        return None
    
    def _extract_text_response(self, response_body: Dict) -> str:
        """Extract text content from response"""
        text_parts = []
        for content_block in response_body.get('content', []):
            if content_block.get('type') == 'text':
                text_parts.append(content_block.get('text', ''))
        return '\n'.join(text_parts)
    
    def chat(self, user_message: str) -> str:
        """Main chat interface"""
        print(f"\n{'='*80}")
        print(f"USER: {user_message}")
        print(f"{'='*80}\n")
        
        try:
            # Get initial response from Claude
            response_body = self._invoke_bedrock(user_message, include_tools=True)
            
            # Handle tool use if needed
            tool_response = self._handle_tool_use(response_body)
            if tool_response:
                final_response = tool_response
            else:
                final_response = self._extract_text_response(response_body)
            
            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": final_response})
            
            return final_response
            
        except Exception as e:
            error_msg = f"Error during chat: {str(e)}"
            print(f"✗ {error_msg}")
            return error_msg
    
    def demo_run(self):
        """Execute a demonstration workflow"""
        print("\n" + "="*80)
        print("DEMO MODE: Cryptographic Operations Workflow")
        print("="*80 + "\n")
        
        demo_tasks = [
            {
                "step": 1,
                "description": "Generate RSA-2048 key pair for web server",
                "prompt": "Generate an RSA-2048 key pair for a web server with common name 'demo.example.com'"
            },
            {
                "step": 2,
                "description": "Create Certificate Signing Request",
                "prompt": "Create a CSR for the generated key with organization 'Demo Corp' and country 'US'"
            },
            {
                "step": 3,
                "description": "Validate cryptographic policies",
                "prompt": "Validate that the generated key and CSR comply with our security policies"
            }
        ]
        
        for task in demo_tasks:
            print(f"\n{'─'*80}")
            print(f"STEP {task['step']}: {task['description']}")
            print(f"{'─'*80}")
            
            response = self.chat(task['prompt'])
            print(f"\nAGENT RESPONSE:\n{response}")
            
            input("\nPress Enter to continue to next step...")
        
        print("\n" + "="*80)
        print("DEMO COMPLETED")
        print("="*80 + "\n")

def main():
    """Main entry point"""
    print("\n" + "="*80)
    print("CRYPTOGRAPHIC AGENT - AWS Bedrock with MCP Plugins")
    print("="*80 + "\n")
    
    try:
        # Initialize configuration
        config = CryptoAgentConfig()
        
        # Create agent
        agent = BedrockCryptoAgent(config)
        
        # Show menu
        while True:
            print("\n" + "─"*80)
            print("SELECT MODE:")
            print("1. Demo Run (Automated workflow with example data)")
            print("2. Interactive Chat (Real-time Q&A on cryptography)")
            print("3. Exit")
            print("─"*80)
            
            choice = input("\nEnter your choice (1-3): ").strip()
            
            if choice == '1':
                agent.demo_run()
            elif choice == '2':
                print("\n" + "="*80)
                print("INTERACTIVE CHAT MODE")
                print("Type 'exit' to return to main menu")
                print("="*80 + "\n")
                
                while True:
                    user_input = input("\nYOU: ").strip()
                    if user_input.lower() in ['exit', 'quit', 'back']:
                        break
                    
                    if not user_input:
                        continue
                    
                    response = agent.chat(user_input)
                    print(f"\nAGENT: {response}")
            elif choice == '3':
                print("\nExiting... Goodbye!")
                sys.exit(0)
            else:
                print("Invalid choice. Please select 1, 2, or 3.")
    
    except Exception as e:
        print(f"\n✗ Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
