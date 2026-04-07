import argparse
import shutil
import os


def clear_tenant_memory(tenant: str, base_dir: str = None):
    """
    Delete memory (both buffer & summary) for a given tenant.

    Args:
        tenant: Tenant identifier (e.g. U1, U2, U3, U4).
        base_dir: Project root directory. Defaults to the parent of this file's directory.
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root = os.path.join(base_dir, ".state", "memory", tenant)
    if os.path.exists(root):
        shutil.rmtree(root)
        print(f"Cleared memory for tenant {tenant}.")
    else:
        print(f"No memory found for tenant {tenant}.")


def main():
    parser = argparse.ArgumentParser(description="Clear per-tenant memory")
    parser.add_argument("--tenant", required=True, help="Tenant identifier (e.g., U1, U2, U3, U4)")
    args = parser.parse_args()

    clear_tenant_memory(args.tenant)


if __name__ == "__main__":
    main()
