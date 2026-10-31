"""Regenerate consolidated knowledge after reviewing the source facts and career.json."""

import json
from pathlib import Path

from agent_cv.knowledge import consolidate, knowledge_markdown
from agent_cv.profile import Profile


def main():
    root = Path(__file__).resolve().parents[1]
    profile_path = root / "data/profile.json"
    career = json.loads((root / "data/career.json").read_text())
    profile = consolidate(Profile.load(profile_path), career)
    profile_path.write_text(json.dumps(profile.model_dump(), ensure_ascii=False, indent=2) + "\n")
    (root / "data/knowledge.md").write_text(knowledge_markdown(profile, career))
    print(f"Consolidated {len(profile.facts)} facts; profile {profile.fingerprint}")


if __name__ == "__main__":
    main()
