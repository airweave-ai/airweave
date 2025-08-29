#!/usr/bin/env python3
"""List available Monke test configurations."""

from pathlib import Path

def main():
    """List all available test configurations."""
    configs_dir = Path(__file__).parent / "configs"

    print("🧪 Available Monke Tests:\n")

    if not configs_dir.exists():
        print("❌ No configs directory found")
        return

    yaml_files = sorted(configs_dir.glob("*.yaml"))

    if not yaml_files:
        print("❌ No test configurations found")
        return

    for config in yaml_files:
        source = config.stem.title()
        print(f"  • {source}: python test.py --config {config.relative_to(Path(__file__).parent)}")

    print("\n💡 Run any test with the command shown above")
    print("📝 Make sure to set up your credentials in env.test first!")


if __name__ == "__main__":
    main()
