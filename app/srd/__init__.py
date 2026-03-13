"""SRD data loader — reads 5e-database JSON files into memory at startup."""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"

# In-memory caches keyed by index
_races: dict[str, dict] = {}
_subraces: dict[str, dict] = {}
_classes: dict[str, dict] = {}
_subclasses: dict[str, dict] = {}
_backgrounds: dict[str, dict] = {}
_spells: dict[str, dict] = {}
_equipment: dict[str, dict] = {}
_skills: dict[str, dict] = {}
_ability_scores: dict[str, dict] = {}
_features: dict[str, dict] = {}
_traits: dict[str, dict] = {}
_proficiencies: dict[str, dict] = {}
_levels: dict[str, dict] = {}

# Skill -> governing ability mapping
SKILL_ABILITIES: dict[str, str] = {}

# All 18 5e skills in order
ALL_SKILLS: list[str] = []


def _load_file(filename: str) -> dict[str, dict]:
    """Load a JSON file and return a dict keyed by 'index'."""
    filepath = _DATA_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        data = json.load(f)
    return {item["index"]: item for item in data}


def load_srd_data() -> None:
    """Load all SRD JSON files into memory. Called once at app startup."""
    global _races, _subraces, _classes, _subclasses, _backgrounds
    global _spells, _equipment, _skills, _ability_scores
    global _features, _traits, _proficiencies, _levels
    global SKILL_ABILITIES, ALL_SKILLS

    _races = _load_file("5e-SRD-Races.json")
    _subraces = _load_file("5e-SRD-Subraces.json")
    _classes = _load_file("5e-SRD-Classes.json")
    _subclasses = _load_file("5e-SRD-Subclasses.json")
    _backgrounds = _load_file("5e-SRD-Backgrounds.json")
    _spells = _load_file("5e-SRD-Spells.json")
    _equipment = _load_file("5e-SRD-Equipment.json")
    _skills = _load_file("5e-SRD-Skills.json")
    _ability_scores = _load_file("5e-SRD-Ability-Scores.json")
    _features = _load_file("5e-SRD-Features.json")
    _traits = _load_file("5e-SRD-Traits.json")
    _proficiencies = _load_file("5e-SRD-Proficiencies.json")
    _levels = _load_file("5e-SRD-Levels.json")

    # Build skill -> ability mapping
    SKILL_ABILITIES.clear()
    ALL_SKILLS.clear()
    for skill in sorted(_skills.values(), key=lambda s: s["name"]):
        ability_index = skill["ability_score"]["index"]
        SKILL_ABILITIES[skill["name"]] = ability_index
        ALL_SKILLS.append(skill["name"])


# --- Public accessors ---


def get_races() -> dict[str, dict]:
    """Return all SRD races keyed by index."""
    return _races


def get_race(index: str) -> dict | None:
    """Return a single race by index, or None."""
    return _races.get(index)


def get_subraces() -> dict[str, dict]:
    """Return all SRD subraces keyed by index."""
    return _subraces


def get_subraces_for_race(race_index: str) -> list[dict]:
    """Return subraces belonging to a given race."""
    return [
        sr for sr in _subraces.values()
        if sr.get("race", {}).get("index") == race_index
    ]


def get_classes() -> dict[str, dict]:
    """Return all SRD classes keyed by index."""
    return _classes


def get_class(index: str) -> dict | None:
    """Return a single class by index, or None."""
    return _classes.get(index)


def get_backgrounds() -> dict[str, dict]:
    """Return all SRD backgrounds keyed by index."""
    return _backgrounds


def get_spells() -> dict[str, dict]:
    """Return all SRD spells keyed by index."""
    return _spells


def get_spells_for_class(class_index: str, max_level: int = 9) -> list[dict]:
    """Return spells available to a class, filtered by max spell level."""
    results = []
    for spell in _spells.values():
        if spell["level"] > max_level:
            continue
        class_indices = [c["index"] for c in spell.get("classes", [])]
        if class_index in class_indices:
            results.append(spell)
    return sorted(results, key=lambda s: (s["level"], s["name"]))


def get_skills() -> dict[str, dict]:
    """Return all SRD skills keyed by index."""
    return _skills


def get_features() -> dict[str, dict]:
    """Return all SRD features keyed by index."""
    return _features


def get_features_for_class(class_index: str, level: int = 1) -> list[dict]:
    """Return class features up to a given level.

    Filters out sub-option features (e.g. individual Fighting Style variants)
    since those are choices, not features granted to every character.
    """
    # Sub-option features have a parent feature reference; we only want
    # top-level features and specific named features like "Second Wind"
    CHOICE_PREFIXES = [
        "Fighting Style:",
        "Maneuver:",
        "Expertise:",
        "Pact Boon:",
        "Eldritch Invocation:",
        "Metamagic:",
        "Hunter's Prey:",
        "Defensive Tactics:",
        "Superior Hunter's Defense:",
    ]
    results = []
    for feat in _features.values():
        feat_class = feat.get("class", {}).get("index", "")
        feat_level = feat.get("level", 0)
        if feat_class == class_index and feat_level <= level:
            # Skip sub-options (they're choices, not auto-granted)
            if any(feat["name"].startswith(prefix) for prefix in CHOICE_PREFIXES):
                continue
            results.append(feat)
    return sorted(results, key=lambda f: (f.get("level", 0), f["name"]))


def get_traits() -> dict[str, dict]:
    """Return all SRD racial traits keyed by index."""
    return _traits


def get_equipment() -> dict[str, dict]:
    """Return all SRD equipment keyed by index."""
    return _equipment


def get_class_skill_choices(class_index: str) -> tuple[int, list[str]]:
    """Return (num_choices, list_of_skill_names) for a class's skill proficiency selection.

    Args:
        class_index: The SRD index of the class (e.g. "fighter").

    Returns:
        Tuple of (number of skills to choose, list of available skill names).
    """
    cls = _classes.get(class_index)
    if not cls:
        return 0, []

    for choice in cls.get("proficiency_choices", []):
        options = choice.get("from", {}).get("options", [])
        skill_names = []
        for opt in options:
            item = opt.get("item", {})
            name = item.get("name", "")
            if name.startswith("Skill: "):
                skill_names.append(name.replace("Skill: ", ""))
        if skill_names:
            return choice.get("choose", 0), skill_names

    return 0, []


def get_class_saving_throws(class_index: str) -> list[str]:
    """Return list of saving throw ability indices for a class."""
    cls = _classes.get(class_index)
    if not cls:
        return []
    return [st["index"] for st in cls.get("saving_throws", [])]


def get_starting_equipment(class_index: str) -> list[dict]:
    """Return the guaranteed starting equipment for a class."""
    cls = _classes.get(class_index)
    if not cls:
        return []
    results = []
    for item in cls.get("starting_equipment", []):
        equip = item.get("equipment", {})
        results.append({
            "name": equip.get("name", "Unknown"),
            "quantity": item.get("quantity", 1),
        })
    return results
