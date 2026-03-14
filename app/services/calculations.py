"""Core D&D 5e math — ability modifiers, proficiency, skill bonuses, etc."""


def ability_modifier(score: int) -> int:
    """Calculate ability modifier from an ability score.

    Args:
        score: Ability score (typically 1-30).

    Returns:
        The modifier (e.g., 10 -> 0, 14 -> +2, 8 -> -1).
    """
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Calculate proficiency bonus from character level.

    Args:
        level: Character level (1-20).

    Returns:
        Proficiency bonus (2 at level 1, scaling to 6 at level 17+).
    """
    return (level - 1) // 4 + 2


def skill_bonus(ability_score: int, level: int, proficiency_type: str = "none") -> int:
    """Calculate total skill bonus.

    Args:
        ability_score: The governing ability score for this skill.
        level: Character level.
        proficiency_type: One of 'none', 'proficient', 'expert'.

    Returns:
        Total bonus = ability_mod + (proficiency_bonus * multiplier).
    """
    mod = ability_modifier(ability_score)
    prof = proficiency_bonus(level)
    multiplier = {"none": 0, "proficient": 1, "expert": 2}.get(proficiency_type, 0)
    return mod + (prof * multiplier)


def saving_throw_bonus(ability_score: int, level: int, proficient: bool) -> int:
    """Calculate saving throw bonus.

    Args:
        ability_score: The ability score for this save.
        level: Character level.
        proficient: Whether the character is proficient in this save.

    Returns:
        Total save bonus.
    """
    mod = ability_modifier(ability_score)
    if proficient:
        mod += proficiency_bonus(level)
    return mod


def passive_perception(wisdom_score: int, level: int, proficiency_type: str = "none") -> int:
    """Calculate passive Perception.

    Args:
        wisdom_score: Wisdom ability score.
        level: Character level.
        proficiency_type: Perception proficiency type.

    Returns:
        10 + Perception skill bonus.
    """
    return 10 + skill_bonus(wisdom_score, level, proficiency_type)


def spell_save_dc(casting_ability_score: int, level: int) -> int:
    """Calculate spell save DC.

    Args:
        casting_ability_score: The spellcasting ability score.
        level: Character level.

    Returns:
        8 + proficiency bonus + casting ability modifier.
    """
    return 8 + proficiency_bonus(level) + ability_modifier(casting_ability_score)


def spell_attack_bonus(casting_ability_score: int, level: int) -> int:
    """Calculate spell attack modifier.

    Args:
        casting_ability_score: The spellcasting ability score.
        level: Character level.

    Returns:
        Proficiency bonus + casting ability modifier.
    """
    return proficiency_bonus(level) + ability_modifier(casting_ability_score)


# Spellcasting ability by class index
SPELLCASTING_ABILITY: dict[str, str] = {
    "bard": "cha",
    "cleric": "wis",
    "druid": "wis",
    "paladin": "cha",
    "ranger": "wis",
    "sorcerer": "cha",
    "warlock": "cha",
    "wizard": "int",
}

# Level 1 spell slots by class (full casters get 2, half-casters get 0 at level 1)
LEVEL_1_SPELL_SLOTS: dict[str, dict[int, int]] = {
    "bard": {1: 2},
    "cleric": {1: 2},
    "druid": {1: 2},
    "sorcerer": {1: 2},
    "warlock": {1: 1},
    "wizard": {1: 2},
    "paladin": {},  # No slots at level 1
    "ranger": {},   # No slots at level 1
}

# Full caster spell slot progression (bard, cleric, druid, sorcerer, wizard)
# Index 0 = level 1, index 19 = level 20. Values are {slot_level: count}.
_FULL_CASTER_SLOTS: list[dict[int, int]] = [
    {1: 2},                                           # Level 1
    {1: 3},                                           # Level 2
    {1: 4, 2: 2},                                     # Level 3
    {1: 4, 2: 3},                                     # Level 4
    {1: 4, 2: 3, 3: 2},                               # Level 5
    {1: 4, 2: 3, 3: 3},                               # Level 6
    {1: 4, 2: 3, 3: 3, 4: 1},                         # Level 7
    {1: 4, 2: 3, 3: 3, 4: 2},                         # Level 8
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},                   # Level 9
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},                   # Level 10
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},             # Level 11
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},             # Level 12
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},       # Level 13
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},       # Level 14
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1}, # Level 15
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1}, # Level 16
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},  # Level 17
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},  # Level 18
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},  # Level 19
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},  # Level 20
]

# Half caster spell slot progression (paladin, ranger) — start at level 2
_HALF_CASTER_SLOTS: list[dict[int, int]] = [
    {},                     # Level 1
    {1: 2},                 # Level 2
    {1: 3},                 # Level 3
    {1: 3},                 # Level 4
    {1: 4, 2: 2},           # Level 5
    {1: 4, 2: 2},           # Level 6
    {1: 4, 2: 3},           # Level 7
    {1: 4, 2: 3},           # Level 8
    {1: 4, 2: 3, 3: 2},     # Level 9
    {1: 4, 2: 3, 3: 2},     # Level 10
    {1: 4, 2: 3, 3: 3},     # Level 11
    {1: 4, 2: 3, 3: 3},     # Level 12
    {1: 4, 2: 3, 3: 3, 4: 1}, # Level 13
    {1: 4, 2: 3, 3: 3, 4: 1}, # Level 14
    {1: 4, 2: 3, 3: 3, 4: 2}, # Level 15
    {1: 4, 2: 3, 3: 3, 4: 2}, # Level 16
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, # Level 17
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}, # Level 18
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}, # Level 19
    {1: 4, 2: 3, 3: 3, 4: 3, 5: 2}, # Level 20
]

# Warlock pact magic — separate progression
_WARLOCK_SLOTS: list[dict[int, int]] = [
    {1: 1},   # Level 1
    {1: 2},   # Level 2
    {2: 2},   # Level 3
    {2: 2},   # Level 4
    {3: 2},   # Level 5
    {3: 2},   # Level 6
    {4: 2},   # Level 7
    {4: 2},   # Level 8
    {5: 2},   # Level 9
    {5: 2},   # Level 10
    {5: 3},   # Level 11
    {5: 3},   # Level 12
    {5: 3},   # Level 13
    {5: 3},   # Level 14
    {5: 3},   # Level 15
    {5: 3},   # Level 16
    {5: 4},   # Level 17
    {5: 4},   # Level 18
    {5: 4},   # Level 19
    {5: 4},   # Level 20
]

FULL_CASTERS = {"bard", "cleric", "druid", "sorcerer", "wizard"}
HALF_CASTERS = {"paladin", "ranger"}

# Weapon proficiency by class — "simple" and "martial" are categories
WEAPON_PROFICIENCIES: dict[str, set[str]] = {
    "barbarian": {"simple", "martial"},
    "bard":      {"simple", "hand-crossbow", "longsword", "rapier", "shortsword"},
    "cleric":    {"simple"},
    "druid":     {"club", "dagger", "dart", "javelin", "mace", "quarterstaff", "scimitar", "sickle", "sling", "spear"},
    "fighter":   {"simple", "martial"},
    "monk":      {"simple", "shortsword"},
    "paladin":   {"simple", "martial"},
    "ranger":    {"simple", "martial"},
    "rogue":     {"simple", "hand-crossbow", "longsword", "rapier", "shortsword"},
    "sorcerer":  {"simple"},
    "warlock":   {"simple"},
    "wizard":    {"simple"},
}


def is_proficient_with_weapon(class_index: str, weapon_data: dict) -> bool:
    """Check if a class is proficient with a weapon.

    Args:
        class_index: SRD class index (e.g. "rogue").
        weapon_data: SRD weapon dict (from Equipment.json).

    Returns:
        True if the class has proficiency with this weapon.
    """
    profs = WEAPON_PROFICIENCIES.get(class_index, set())
    weapon_cat = weapon_data.get("weapon_category", "").lower()  # "Simple" or "Martial"
    weapon_idx = weapon_data.get("index", "")
    if weapon_cat in profs:
        return True
    return weapon_idx in profs


def weapon_ability_score(weapon_data: dict, str_score: int, dex_score: int) -> tuple[int, str]:
    """Determine which ability score to use for a weapon attack.

    Melee uses STR, ranged uses DEX, finesse uses whichever is higher.

    Args:
        weapon_data: SRD weapon dict.
        str_score: Character's Strength score.
        dex_score: Character's Dexterity score.

    Returns:
        Tuple of (score_value, ability_name).
    """
    properties = [p["index"] for p in weapon_data.get("properties", [])]
    weapon_range = weapon_data.get("weapon_range", "Melee")

    if "finesse" in properties:
        if dex_score >= str_score:
            return dex_score, "DEX"
        return str_score, "STR"
    if weapon_range == "Ranged":
        return dex_score, "DEX"
    return str_score, "STR"


def weapon_attack_bonus(ability_score: int, level: int, proficient: bool, magic_bonus: int = 0) -> int:
    """Calculate weapon attack bonus.

    Args:
        ability_score: The relevant ability score (STR or DEX).
        level: Character level (for proficiency bonus).
        proficient: Whether the character is proficient with this weapon.
        magic_bonus: Magic weapon bonus (+1, +2, +3).

    Returns:
        Total attack bonus.
    """
    bonus = ability_modifier(ability_score)
    if proficient:
        bonus += proficiency_bonus(level)
    bonus += magic_bonus
    return bonus


def spell_slots_for_level(class_index: str, level: int) -> dict[int, int]:
    """Get spell slot counts for a class at a given level.

    Args:
        class_index: SRD class index (e.g. "wizard", "paladin").
        level: Character level (1-20).

    Returns:
        Dict of {slot_level: count}. Empty dict for non-casters.
    """
    idx = max(0, min(level - 1, 19))
    if class_index in FULL_CASTERS:
        return dict(_FULL_CASTER_SLOTS[idx])
    if class_index in HALF_CASTERS:
        return dict(_HALF_CASTER_SLOTS[idx])
    if class_index == "warlock":
        return dict(_WARLOCK_SLOTS[idx])
    return {}


def max_spell_level(class_index: str, level: int) -> int:
    """Get the highest spell level available to a class at a given level.

    Args:
        class_index: SRD class index.
        level: Character level (1-20).

    Returns:
        Highest spell level (0 if no spellcasting at that level).
    """
    slots = spell_slots_for_level(class_index, level)
    return max(slots.keys()) if slots else 0


def hit_points_at_level(hit_die: int, con_mod: int, level: int) -> int:
    """Calculate max HP at a given level.

    Level 1: hit_die max + CON mod.
    Each subsequent level: average hit die roll (rounded up) + CON mod.

    Args:
        hit_die: Hit die size (e.g. 10 for d10).
        con_mod: Constitution modifier.
        level: Character level (1-20).

    Returns:
        Max HP.
    """
    avg_roll = (hit_die // 2) + 1  # e.g. d10 -> 6, d8 -> 5, d6 -> 4
    hp = hit_die + con_mod  # Level 1
    hp += (avg_roll + con_mod) * (level - 1)  # Levels 2+
    return max(1, hp)


# Cantrips known at level 1 by class
CANTRIPS_KNOWN: dict[str, int] = {
    "bard": 2,
    "cleric": 3,
    "druid": 2,
    "sorcerer": 4,
    "warlock": 2,
    "wizard": 3,
}

# Cantrips known scaling — {class: [(level_threshold, cantrips_known), ...]}
CANTRIPS_SCALING: dict[str, list[tuple[int, int]]] = {
    "bard":     [(1, 2), (4, 3), (10, 4)],
    "cleric":   [(1, 3), (4, 4), (10, 5)],
    "druid":    [(1, 2), (4, 3), (10, 4)],
    "sorcerer": [(1, 4), (4, 5), (10, 6)],
    "warlock":  [(1, 2), (4, 3), (10, 4)],
    "wizard":   [(1, 3), (4, 4), (10, 5)],
}


def cantrips_known_at_level(class_index: str, level: int) -> int:
    """Get number of cantrips known for a class at a given level.

    Args:
        class_index: SRD class index.
        level: Character level (1-20).

    Returns:
        Number of cantrips known (0 if non-caster).
    """
    thresholds = CANTRIPS_SCALING.get(class_index, [])
    result = 0
    for threshold_level, count in thresholds:
        if level >= threshold_level:
            result = count
    return result


# Spells known/prepared at level 1
# For preparation casters (cleric, druid, paladin): WIS/CHA mod + level (min 1)
# For known casters: fixed number
SPELLS_KNOWN_LEVEL_1: dict[str, int | str] = {
    "bard": 4,
    "cleric": "prepared",   # WIS mod + cleric level
    "druid": "prepared",    # WIS mod + druid level
    "paladin": "prepared",  # CHA mod + half paladin level
    "ranger": 0,            # No spells at level 1
    "sorcerer": 2,
    "warlock": 2,
    "wizard": 6,            # Spellbook: 6 spells, prepare INT mod + wizard level
}

# Known-caster spell progression — {class: [(level_threshold, spells_known), ...]}
SPELLS_KNOWN_SCALING: dict[str, list[tuple[int, int]]] = {
    "bard":     [(1, 4), (2, 5), (3, 6), (4, 7), (5, 8), (6, 9), (7, 10), (8, 11), (9, 12), (10, 14), (11, 15), (13, 16), (14, 18), (15, 19), (17, 20), (18, 22)],
    "ranger":   [(2, 2), (3, 3), (5, 4), (7, 5), (9, 6), (11, 7), (13, 8), (15, 9), (17, 10), (19, 11)],
    "sorcerer": [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (11, 12), (13, 13), (15, 14), (17, 15)],
    "warlock":  [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (11, 11), (13, 12), (15, 13), (17, 14), (19, 15)],
}


def spells_known_at_level(class_index: str, level: int) -> int | str:
    """Get number of spells known or 'prepared' for a class at a level.

    Args:
        class_index: SRD class index.
        level: Character level (1-20).

    Returns:
        Int count for known-casters, or 'prepared' for preparation casters.
    """
    if class_index in ("cleric", "druid", "paladin", "wizard"):
        return "prepared"
    thresholds = SPELLS_KNOWN_SCALING.get(class_index, [])
    result = 0
    for threshold_level, count in thresholds:
        if level >= threshold_level:
            result = count
    return result
