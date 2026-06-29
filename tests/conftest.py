"""Pytest configuration for darwinloop tests."""
import sys
from pathlib import Path

# Ensure src/ is on the path when running tests from the darwinloop/ root
sys.path.insert(0, str(Path(__file__).parent / "src"))
