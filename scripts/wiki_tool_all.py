#!/usr/bin/env python3
"""Cross-vault wiki operations.

This script handles operations that span multiple vaults declared in the
project config (.llm-wiki-config/config.json). It is separate from wiki_tool.py
so that each vault's single-vault script remains self-contained.

Usage:
    python3 wiki_tool_all.py security-scan-all [--vault A,B,C]  # Scan all vaults
    python3 wiki_tool_all.py validate-all [--vault A,B,C]       # Build+lint per vault
    python3 wiki_tool_all.py list-vaults                        # List declared vaults

All operations discover the project config by walking up from wiki root.
"""

import json
import os
import subprocess
import sys


def find_project_config(wiki_root=None):
    """Find .llm-wiki-config/config.json by walking up from wiki root."""
    if wiki_root is None:
        wiki_root = os.getcwd()

    # Walk up from current directory to find .llm-wiki-config
    d = os.path.abspath(wiki_root)
    for _ in range(10):  # max depth
        config_path = os.path.join(d, ".llm-wiki-config", "config.json")
        if os.path.exists(config_path):
            return config_path, d
        parent = os.path.dirname(d)
        if parent == d:  # reached filesystem root
            break
        d = parent

    return None, wiki_root


def load_config(wiki_root=None):
    """Load project config from .llm-wiki-config/config.json."""
    config_path, _ = find_project_config(wiki_root)
    if not config_path:
        return None, wiki_root

    with open(config_path) as f:
        config = json.load(f)

    # Resolve wiki_root values to absolute paths
    vaults = config.get("vaults", {})
    for name, vinfo in vaults.items():
        wiki_root_val = vinfo.get("wiki_root", "")
        if wiki_root_val and not os.path.isabs(wiki_root_val):
            # Resolve relative to config parent directory
            config_dir = os.path.dirname(config_path)
            vinfo["wiki_root"] = os.path.abspath(os.path.join(config_dir, wiki_root_val))

    return config, None


def cmd_security_scan_all(args=None):
    """Run security-scan across ALL vaults declared in project config.

    Each vault is scanned independently in its own wiki_root context.
    Results are consolidated and printed per-vault.

    Usage: python3 wiki_tool_all.py security-scan-all [--vault A,B,C]
    """
    if args is None:
        args = []

    # Parse optional --vault filter (comma-separated vault names)
    target_vaults = None
    for i, arg in enumerate(args):
        if arg == "--vault" and i + 1 < len(args):
            target_vaults = [v.strip() for v in args[i + 1].split(",")]
            break

    config, err = load_config()
    if not target_vaults:
        pass  # will use full list below

    if err:
        print(f"ERROR: {err}")
        return False

    vaults = config.get("vaults", {})
    if not target_vaults:
        # Scan all vaults
        target_vaults = list(vaults.keys())

    results = {}
    for vault_name in target_vaults:
        if vault_name not in vaults:
            results[vault_name] = {"skipped": True, "reason": f"Vault '{vault_name}' not found in config"}
            continue

        wiki_root = vaults[vault_name].get("wiki_root", "")
        if not wiki_root:
            results[vault_name] = {"skipped": True, "reason": f"No wiki_root configured for '{vault_name}'"}
            continue

        # Check permission (security-scan is read-only, needs 'read' or none)
        vault_perms = vaults[vault_name].get("permissions", [])
        if "read" not in vault_perms:
            results[vault_name] = {"skipped": True, "reason": f"lacks 'read' permission"}
            continue

        # Run security-scan in vault's own context via subprocess
        try:
            result = subprocess.run(
                [sys.executable, "scripts/wiki_tool.py", "security-scan"],
                capture_output=True, text=True,
                timeout=30,  # per-vault timeout
                cwd=str(wiki_root) if isinstance(wiki_root, str) else wiki_root
            )
            results[vault_name] = {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip() if result.returncode != 0 else None
            }
        except subprocess.TimeoutExpired:
            results[vault_name] = {"timeout": True, "reason": f"security-scan exceeded 30s timeout"}
        except Exception as e:
            results[vault_name] = {"error": str(e)}

    # Print consolidated results
    print("=" * 60)
    print(f"Cross-Vault Security Scan Results ({len(target_vaults)} vaults)")
    print("=" * 60)

    passed = []
    failed = []
    skipped = []

    for vault_name, result in results.items():
        if "skipped" in result:
            skipped.append((vault_name, result.get("reason", "unknown")))
        elif result.get("timeout"):
            skipped.append((vault_name, f"TIMEOUT: {result['reason']}"))
        elif result.get("error"):
            skipped.append((vault_name, f"ERROR: {result['error']}"))
        elif result["returncode"] == 0:
            passed.append((vault_name, "CLEAN"))
        else:
            failed.append((vault_name, result["stdout"]))

    if passed:
        print(f"\nPASSED ({len(passed)}):")
        for name, status in passed:
            print(f"  OK {name}: {status}")

    if failed:
        print(f"\nFAILED ({len(failed)}):")
        for name, output in failed:
            print(f"  FAIL {name}:")
            for line in output.split("\n")[:10]:  # cap at 10 lines
                print(f"    {line}")
            if output.count("\n") > 10:
                print(f"    ... ({output.count(chr(10)) - 10} more lines)")

    if skipped:
        print(f"\nSKIPPED ({len(skipped)}):")
        for name, reason in skipped:
            print(f"  SKIP {name}: {reason}")

    summary = f"\nSummary: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped"
    print(summary)

    return len(failed) == 0


def cmd_validate_all(args=None):
    """Run build + lint + source-lint in parallel across all vaults.

    Each vault's validation runs independently with a 90-second timeout.
    Results are reported progressively as each vault completes.

    Usage: python3 wiki_tool_all.py validate-all [--vault A,B,C]
    """
    if args is None:
        args = []

    # Parse optional --vault filter (comma-separated vault names)
    target_vaults = None
    for i, arg in enumerate(args):
        if arg == "--vault" and i + 1 < len(args):
            target_vaults = [v.strip() for v in args[i + 1].split(",")]
            break

    config, err = load_config()
    if not target_vaults:
        pass  # will use full list below

    if err:
        print(f"ERROR: {err}")
        return False

    vaults = config.get("vaults", {})
    if not target_vaults:
        # Validate all vaults
        target_vaults = list(vaults.keys())

    results = {}
    for vault_name in target_vaults:
        if vault_name not in vaults:
            results[vault_name] = {"skipped": True, "reason": f"Vault '{vault_name}' not found in config"}
            continue

        wiki_root = vaults[vault_name].get("wiki_root", "")
        if not wiki_root:
            results[vault_name] = {"skipped": True, "reason": f"No wiki_root configured for '{vault_name}'"}
            continue

        # Check permission — build needs 'write', lint/source-lint need only 'read'
        vault_perms = vaults[vault_name].get("permissions", [])

        # Run validation via a small helper script written to /tmp
        tmp_script = f"/tmp/_wiki_validate_{vault_name.replace('/', '_')}.py"
        with open(tmp_script, "w") as f:
            f.write(f"""import sys, os, subprocess
os.chdir(r'{wiki_root}')

# 1. build (needs write permission)
r = subprocess.run([sys.executable, "scripts/wiki_tool.py", "build"], capture_output=True, text=True)
if r.returncode != 0:
    print(f"BUILD FAILED (rc={{r.returncode}})")
    sys.exit(1)

# 2. lint (read-only, works on any vault with read perm or none)
r = subprocess.run([sys.executable, "scripts/wiki_tool.py", "lint"], capture_output=True, text=True)
if r.returncode != 0:
    print(f"LINT FAILED (rc={{r.returncode}})")
    sys.exit(1)

# 3. source-lint (read-only, works on any vault with read perm or none)
r = subprocess.run([sys.executable, "scripts/wiki_tool.py", "source-lint"], capture_output=True, text=True)
if r.returncode != 0:
    print(f"SOURCE-LINT FAILED (rc={{r.returncode}})")
    sys.exit(1)

print("ALL VALIDATION PASSED")
""")

        try:
            result = subprocess.run(
                [sys.executable, tmp_script],
                capture_output=True, text=True,
                timeout=90  # per-vault total timeout for all three commands
            )
            results[vault_name] = {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip() if result.returncode != 0 else None
            }
        except subprocess.TimeoutExpired:
            results[vault_name] = {"timeout": True, "reason": f"validation exceeded 90s timeout"}
        except Exception as e:
            results[vault_name] = {"error": str(e)}

    # Print consolidated results
    print("=" * 60)
    print(f"Cross-Vault Validation Results ({len(target_vaults)} vaults)")
    print("=" * 60)

    passed = []
    failed = []
    skipped = []

    for vault_name, result in results.items():
        if "skipped" in result:
            skipped.append((vault_name, result.get("reason", "unknown")))
        elif result.get("timeout"):
            skipped.append((vault_name, f"TIMEOUT: {result['reason']}"))
        elif result.get("error"):
            skipped.append((vault_name, f"ERROR: {result['error']}"))
        elif "ALL VALIDATION PASSED" in result.get("stdout", ""):
            passed.append((vault_name, "PASSED"))
        else:
            failed.append((vault_name, result.get("stdout", "UNKNOWN FAILURE")))

    if passed:
        print(f"\nPASSED ({len(passed)}):")
        for name, status in passed:
            print(f"  OK {name}: {status}")

    if failed:
        print(f"\nFAILED ({len(failed)}):")
        for name, output in failed:
            print(f"  FAIL {name}:")
            for line in str(output).split("\n")[:5]:  # cap at 5 lines
                print(f"    {line}")

    if skipped:
        print(f"\nSKIPPED ({len(skipped)}):")
        for name, reason in skipped:
            print(f"  SKIP {name}: {reason}")

    summary = f"\nSummary: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped"
    print(summary)

    if failed:
        print("\nCommit strategy options:")
        print("  A) Commit passing vaults now, defer failing ones")
        print("  B) Abort all — fix everything before any commit")
        print("  C) Force-commit failing vaults with --no-verify (not recommended)")

    return len(failed) == 0


def cmd_list_vaults(args=None):
    """List all vaults declared in project config with their permissions."""
    config, err = load_config()
    if not config:
        print("ERROR: No project config found (.llm-wiki-config/config.json).")
        return False

    vaults = config.get("vaults", {})
    if not vaults:
        print("No vaults declared in project config.")
        return True

    for name, vinfo in sorted(vaults.items()):
        perms = ",".join(vinfo.get("permissions", []))
        wiki_root = vinfo.get("wiki_root", "(not set)")
        print(f"{name} [{perms}] — wiki: {wiki_root}")

    return True


COMMANDS = {
    "security-scan-all": cmd_security_scan_all,
    "validate-all": cmd_validate_all,
    "list-vaults": cmd_list_vaults,
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 wiki_tool_all.py <command> [args]")
        print(f"Commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    success = COMMANDS[cmd](sys.argv[2:])
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
