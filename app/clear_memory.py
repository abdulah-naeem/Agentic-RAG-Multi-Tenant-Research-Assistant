import argparse
import shutil
import os

def clear_tenant_memory(tenant: str):
    """
    Delete memory (both buffer & summary) for a given tenant.
    """
    root = os.path.join(".state", "memory", tenant)
    if os.path.exists(root):
        shutil.rmtree(root)
    else:
        pass

def main():
    parser = argparse.ArgumentParser(description="Clear per-tenant memory")
    parser.add_argument("--tenant", required=True, help="Tenant identifier (e.g., U1, U2, U3, U4)")
    args = parser.parse_args()
    
    clear_tenant_memory(args.tenant)

if __name__ == "__main__":
    main()
