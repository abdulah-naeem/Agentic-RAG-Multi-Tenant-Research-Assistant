import argparse
import os
import yaml
import sys

# Add the parent directory (project root) to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Now Python can find agents.controller
from agents.controller import agent

from app import clear_memory  # assuming clear_memory.py is in same folder

def load_cfg(path: str):
    """
    Load YAML configuration file.
    """
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

class Memory:
    """
    Simple memory holder for tenant-scoped memory mode.
    """
    def __init__(self, kind: str):
        self.kind = kind  # 'buffer', 'summary', or 'none'

def single_turn(base_dir, tenant, query, cfg, memory: Memory):
    """
    Process a single query and exit.
    """
    print(agent(base_dir, tenant, query, cfg, memory=memory))

def chat_repl(base_dir, tenant, cfg, memory: Memory):
    """
    Interactive multi-turn chat REPL.
    """
    print(f"Starting chat REPL for tenant {tenant} (memory={memory.kind})")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue

        # Commands
        if user_input.lower() == "/exit":
            print("Exiting REPL.")
            break
        elif user_input.lower() == "/clear":
            clear_memory.clear_tenant_memory(tenant)
            continue
        elif user_input.lower().startswith("/mode"):
            mode = user_input.split()[-1].lower()
            if mode in ["buffer", "summary", "none"]:
                memory.kind = mode
                print(f"Memory mode switched to {mode}")
            else:
                print("Invalid memory mode. Choose buffer, summary, or none.")
            continue

        # Normal chat query
        response = agent(base_dir, tenant, user_input, cfg, memory=memory)
        print(f"Agent: {response}")

def main():
    parser = argparse.ArgumentParser(description="Tenant-scoped Chat/Query Agent")
    parser.add_argument("--tenant", required=True, help="U1, U2, U3, U4")
    parser.add_argument("--query", help="Single-turn query")
    parser.add_argument("--chat", action="store_true", help="Start interactive chat REPL")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--memory", choices=["buffer","summary","none"], default="summary")
    args = parser.parse_args()

    cfg = load_cfg(args.config)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    memory = Memory(args.memory)

    # Mode selection
    if args.chat:
        chat_repl(base_dir, args.tenant, cfg, memory)
    elif args.query:
        single_turn(base_dir, args.tenant, args.query, cfg, memory)
    else:
        print("Error: Specify either --query for single-turn or --chat for REPL.")

if __name__ == "__main__":
    main()
