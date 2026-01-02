"""Validate that the system is properly set up and configured."""

import asyncio
import os
import sys
from pathlib import Path


async def check_env_file() -> bool:
    """Check if .env file exists and has required variables."""
    print("Checking environment configuration...")

    env_path = Path(".env")
    if not env_path.exists():
        print("  ❌ .env file not found!")
        print("  → Run: cp .env.example .env")
        return False

    # Read .env file
    with open(env_path) as f:
        env_content = f.read()

    required_vars = ["ANTHROPIC_API_KEY", "DATABASE_URL", "REDIS_URL"]
    missing_vars = []

    for var in required_vars:
        if var not in env_content:
            missing_vars.append(var)
        elif f"{var}=your_" in env_content or f"{var}=" in env_content.split(var)[1][:20]:
            if var == "ANTHROPIC_API_KEY":
                print(f"  ⚠️  {var} appears to be a placeholder")
                print("  → Set your actual Anthropic API key in .env")
                return False

    if missing_vars:
        print(f"  ❌ Missing variables: {', '.join(missing_vars)}")
        return False

    print("  ✓ Environment file configured")
    return True


async def check_docker() -> bool:
    """Check if Docker is installed and running."""
    print("\nChecking Docker...")

    # Check if docker command exists
    result = await asyncio.create_subprocess_exec(
        "docker", "version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await result.communicate()

    if result.returncode != 0:
        print("  ❌ Docker is not running!")
        print("  → Start Docker Desktop or Docker daemon")
        return False

    print("  ✓ Docker is running")

    # Check if docker-compose exists
    result = await asyncio.create_subprocess_exec(
        "docker-compose", "version",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await result.communicate()

    if result.returncode != 0:
        print("  ❌ docker-compose not found!")
        print("  → Install docker-compose")
        return False

    print("  ✓ docker-compose is available")
    return True


async def check_project_structure() -> bool:
    """Check if all required directories and files exist."""
    print("\nChecking project structure...")

    required_paths = [
        "src/agents/base.py",
        "src/agents/orchestrator.py",
        "src/agents/order_agent.py",
        "src/agents/inventory_agent.py",
        "src/agents/kitchen_agent.py",
        "src/agents/delivery_agent.py",
        "src/agents/support_agent.py",
        "src/api/routes.py",
        "src/api/websocket.py",
        "src/main.py",
        "docker-compose.yml",
        "Dockerfile",
        "pyproject.toml",
    ]

    missing = []
    for path in required_paths:
        if not Path(path).exists():
            missing.append(path)

    if missing:
        print(f"  ❌ Missing files:")
        for path in missing:
            print(f"     - {path}")
        return False

    print("  ✓ All required files present")
    return True


async def check_python_version() -> bool:
    """Check if Python version is 3.11+."""
    print("\nChecking Python version...")

    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"  ❌ Python {version.major}.{version.minor} detected")
        print("  → Python 3.11+ required")
        return False

    print(f"  ✓ Python {version.major}.{version.minor} detected")
    return True


async def check_services() -> bool:
    """Check if services are running (if docker-compose is up)."""
    print("\nChecking running services...")

    result = await asyncio.create_subprocess_exec(
        "docker-compose", "ps",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await result.communicate()

    if result.returncode != 0:
        print("  ℹ️  Services not running (run 'docker-compose up -d')")
        return True  # Not a failure, just not started yet

    output = stdout.decode()

    if "restaurant_app" in output and "Up" in output:
        print("  ✓ Application service is running")

        # Try to hit the health endpoint
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/health", timeout=5.0)
                if response.status_code == 200:
                    print("  ✓ API is responding")
                else:
                    print(f"  ⚠️  API returned status {response.status_code}")
        except ImportError:
            print("  ℹ️  httpx not installed, skipping API check")
        except Exception as e:
            print(f"  ⚠️  API not responding: {e}")

    else:
        print("  ℹ️  Services not started yet")
        print("  → Run: docker-compose up -d")

    return True


async def main() -> None:
    """Run all validation checks."""
    print("\n" + "=" * 60)
    print("  Multi-Agent Restaurant Orchestrator - Setup Validation")
    print("=" * 60 + "\n")

    checks = [
        ("Python Version", check_python_version),
        ("Environment", check_env_file),
        ("Docker", check_docker),
        ("Project Structure", check_project_structure),
        ("Services", check_services),
    ]

    results = []
    for name, check in checks:
        try:
            result = await check()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ Error during {name} check: {e}")
            results.append((name, False))

    print("\n" + "=" * 60)
    print("  Validation Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✅ All checks passed! System is ready.")
        print("\nNext steps:")
        print("  1. Start services: docker-compose up -d")
        print("  2. Seed data: docker-compose exec app python scripts/seed_data.py")
        print("  3. Test API: curl http://localhost:8000/health")
        print("  4. View docs: http://localhost:8000/docs")
    else:
        print("\n❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)

    print()


if __name__ == "__main__":
    asyncio.run(main())
