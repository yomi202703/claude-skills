import sys
from pathlib import Path

# Make the skill's scripts importable for property tests
SKILL_DIR = Path.home() / ".claude/skills/xlsx"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
