"""Business logic for creating a new character from form data."""

from app.extensions import db
from app.models.character import (
    AbilityScores,
    Character,
    CharacterClass,
    ClassFeature,
    InventoryItem,
    KnownSpell,
    SavingThrowProficiency,
    SkillProficiency,
    SpellSlot,
)
from app.services.calculations import (
    SPELLCASTING_ABILITY,
    ability_modifier,
    hit_points_at_level,
    passive_perception,
    proficiency_bonus,
    spell_slots_for_level,
)
from app.srd import (
    get_class,
    get_class_saving_throws,
    get_features_for_class,
    get_race,
    get_starting_equipment,
    get_traits,
)


def create_character(
    user_id: int,
    name: str,
    race_index: str,
    race_name: str,
    class_index: str,
    class_name: str,
    background: str,
    alignment: str,
    scores: dict[str, int],
    skill_choices: list[str],
    background_skills: list[str],
    level: int = 1,
    spell_indices: list[str] | None = None,
    cantrip_indices: list[str] | None = None,
    equipment_text: str = "",
    personality_traits: str = "",
    ideals: str = "",
    bonds: str = "",
    flaws: str = "",
) -> Character:
    """Create a fully populated character at the specified level.

    Args:
        user_id: Owner user ID.
        name: Character name.
        race_index: SRD race index or 'custom'.
        race_name: Display name for race.
        class_index: SRD class index or 'custom'.
        class_name: Display name for class.
        background: Background name.
        alignment: Alignment string.
        scores: Dict with keys str/dex/con/int/wis/cha -> base scores (before racial bonuses).
        skill_choices: List of skill names chosen from class options.
        background_skills: List of skill names from background.
        level: Character level (1-20). Defaults to 1.
        spell_indices: Optional list of spell SRD indices for spellcasters.
        cantrip_indices: Optional list of cantrip SRD indices.
        equipment_text: Freeform equipment text for custom entry.
        personality_traits: Personality traits text.
        ideals: Ideals text.
        bonds: Bonds text.
        flaws: Flaws text.

    Returns:
        The created Character instance (already committed to DB).
    """
    level = max(1, min(20, level))
    # Apply racial ability bonuses
    final_scores = dict(scores)
    race_data = get_race(race_index)
    if race_data:
        for bonus in race_data.get("ability_bonuses", []):
            ability = bonus["ability_score"]["index"]
            final_scores[ability] = final_scores.get(ability, 10) + bonus["bonus"]

    # Get class data
    class_data = get_class(class_index)
    hit_die = class_data["hit_die"] if class_data else 8

    # Calculate HP at the given level
    con_mod = ability_modifier(final_scores.get("con", 10))
    max_hp = hit_points_at_level(hit_die, con_mod, level)

    # Calculate AC: 10 + DEX mod (default, no armor)
    dex_mod = ability_modifier(final_scores.get("dex", 10))
    armor_class = 10 + dex_mod

    # Speed from race
    speed = race_data.get("speed", 30) if race_data else 30

    # Figure out perception proficiency for passive perception
    all_proficient_skills = set(skill_choices) | set(background_skills)
    perception_prof = "proficient" if "Perception" in all_proficient_skills else "none"
    passive_perc = passive_perception(final_scores.get("wis", 10), level, perception_prof)

    # Create the character
    character = Character(
        user_id=user_id,
        name=name,
        race=race_name,
        race_index=race_index,
        background=background,
        alignment=alignment,
        level=level,
        max_hp=max_hp,
        current_hp=max_hp,
        hit_dice_total=level,
        hit_dice_remaining=level,
        armor_class=armor_class,
        speed=speed,
        proficiency_bonus=proficiency_bonus(level),
    )
    character.personality_traits = personality_traits
    character.ideals = ideals
    character.bonds = bonds
    character.flaws = flaws

    db.session.add(character)
    db.session.flush()  # Get character.id

    # Ability scores
    ability = AbilityScores(
        character_id=character.id,
        strength=final_scores.get("str", 10),
        dexterity=final_scores.get("dex", 10),
        constitution=final_scores.get("con", 10),
        intelligence=final_scores.get("int", 10),
        wisdom=final_scores.get("wis", 10),
        charisma=final_scores.get("cha", 10),
    )
    db.session.add(ability)

    # Class
    char_class = CharacterClass(
        character_id=character.id,
        class_name=class_name,
        class_index=class_index,
        level=level,
        hit_die=hit_die,
    )
    db.session.add(char_class)

    # Skill proficiencies
    for skill_name in all_proficient_skills:
        sp = SkillProficiency(
            character_id=character.id,
            skill_name=skill_name,
            proficiency_type="proficient",
        )
        db.session.add(sp)

    # Saving throw proficiencies
    save_abilities = get_class_saving_throws(class_index)
    for ability_idx in ["str", "dex", "con", "int", "wis", "cha"]:
        stp = SavingThrowProficiency(
            character_id=character.id,
            ability=ability_idx,
            proficient=ability_idx in save_abilities,
        )
        db.session.add(stp)

    # Class features (up to character level)
    features = get_features_for_class(class_index, level=level)
    for feat in features:
        cf = ClassFeature(
            character_id=character.id,
            feature_name=feat["name"],
            description="\n".join(feat.get("desc", [])),
            source=class_name,
        )
        db.session.add(cf)

    # Racial traits
    if race_data:
        traits = get_traits()
        for trait_ref in race_data.get("traits", []):
            trait = traits.get(trait_ref.get("index", ""))
            if trait:
                cf = ClassFeature(
                    character_id=character.id,
                    feature_name=trait["name"],
                    description="\n".join(trait.get("desc", [])),
                    source=race_name,
                )
                db.session.add(cf)

    # Starting equipment
    if equipment_text:
        for line in equipment_text.strip().split("\n"):
            line = line.strip()
            if line:
                item = InventoryItem(
                    character_id=character.id,
                    name=line,
                    quantity=1,
                )
                db.session.add(item)
    else:
        starting_equip = get_starting_equipment(class_index)
        for eq in starting_equip:
            item = InventoryItem(
                character_id=character.id,
                name=eq["name"],
                quantity=eq["quantity"],
            )
            db.session.add(item)

    # Spell slots for spellcasters
    slots = spell_slots_for_level(class_index, level)
    for slot_level, total in slots.items():
        ss = SpellSlot(
            character_id=character.id,
            slot_level=slot_level,
            total=total,
            used=0,
        )
        db.session.add(ss)

    # Known spells
    from app.srd import get_spells

    all_spells = get_spells()
    if cantrip_indices:
        for idx in cantrip_indices:
            spell = all_spells.get(idx)
            if spell:
                ks = KnownSpell(
                    character_id=character.id,
                    spell_name=spell["name"],
                    spell_index=idx,
                    spell_level=0,
                    prepared=True,
                    source="class",
                )
                db.session.add(ks)

    if spell_indices:
        for idx in spell_indices:
            spell = all_spells.get(idx)
            if spell:
                ks = KnownSpell(
                    character_id=character.id,
                    spell_name=spell["name"],
                    spell_index=idx,
                    spell_level=spell["level"],
                    prepared=True,
                    source="class",
                )
                db.session.add(ks)

    db.session.commit()
    return character
