import json

from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.characters import characters_bp
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
from app.services import calculations as calc
from app.services.character_creator import create_character
from app.srd import (
    ALL_SKILLS,
    SKILL_ABILITIES,
    get_all_weapons,
    get_class,
    get_class_skill_choices,
    get_classes,
    get_features_for_class,
    get_races,
    get_spells_for_class,
    get_subraces_for_race,
)


@characters_bp.route("/")
@login_required
def character_list():
    """Show all characters belonging to the current user."""
    characters = Character.query.filter_by(user_id=current_user.id).all()
    return render_template("characters/list.html", characters=characters)


@characters_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """Character creation form."""
    races = get_races()
    classes = get_classes()

    if request.method == "POST":
        return _handle_create(request.form)

    # Build data for the template
    race_list = sorted(races.values(), key=lambda r: r["name"])
    class_list = sorted(classes.values(), key=lambda c: c["name"])

    # Prepare JSON data for dynamic form behavior
    race_data_json = {}
    for r in race_list:
        subraces = get_subraces_for_race(r["index"])
        race_data_json[r["index"]] = {
            "name": r["name"],
            "speed": r["speed"],
            "ability_bonuses": [
                {"ability": ab["ability_score"]["index"], "bonus": ab["bonus"]}
                for ab in r.get("ability_bonuses", [])
            ],
            "subraces": [{"index": sr["index"], "name": sr["name"]} for sr in subraces],
        }

    class_data_json = {}
    for c in class_list:
        num_skills, skill_options = get_class_skill_choices(c["index"])
        is_caster = c["index"] in calc.SPELLCASTING_ABILITY

        spells_by_level = {}
        if is_caster:
            # Load all spell levels (JS filters by selected character level)
            spells = get_spells_for_class(c["index"], max_level=9)
            for s in spells:
                lvl = s["level"]
                if lvl not in spells_by_level:
                    spells_by_level[lvl] = []
                spells_by_level[lvl].append({
                    "index": s["index"],
                    "name": s["name"],
                    "level": s["level"],
                })

        class_data_json[c["index"]] = {
            "name": c["name"],
            "hit_die": c["hit_die"],
            "num_skill_choices": num_skills,
            "skill_options": skill_options,
            "saving_throws": [st["index"] for st in c.get("saving_throws", [])],
            "is_caster": is_caster,
            "casting_ability": calc.SPELLCASTING_ABILITY.get(c["index"], ""),
            "cantrips_known": calc.CANTRIPS_KNOWN.get(c["index"], 0),
            "spells_by_level": spells_by_level,
            "cantrips_scaling": calc.CANTRIPS_SCALING.get(c["index"], []),
            "spells_known_scaling": calc.SPELLS_KNOWN_SCALING.get(c["index"], []),
            "is_prepared_caster": c["index"] in ("cleric", "druid", "paladin", "wizard"),
            "is_full_caster": c["index"] in calc.FULL_CASTERS,
            "is_half_caster": c["index"] in calc.HALF_CASTERS,
        }

    return render_template(
        "characters/create.html",
        race_list=race_list,
        class_list=class_list,
        race_data_json=json.dumps(race_data_json),
        class_data_json=json.dumps(class_data_json),
        standard_array=[15, 14, 13, 12, 10, 8],
        all_skills=ALL_SKILLS,
        skill_abilities=SKILL_ABILITIES,
    )


def _handle_create(form):
    """Process the character creation form submission."""
    name = form.get("name", "").strip()
    race_index = form.get("race", "custom")
    class_index = form.get("class", "custom")
    background = form.get("background", "").strip() or "Custom"
    alignment = form.get("alignment", "")

    # Character level
    try:
        level = int(form.get("level", 1))
        level = max(1, min(20, level))
    except (ValueError, TypeError):
        level = 1

    # Race name
    races = get_races()
    if race_index in races:
        race_name = races[race_index]["name"]
    else:
        race_name = form.get("custom_race_name", "Custom Race").strip()

    # Class name
    classes = get_classes()
    if class_index in classes:
        class_name = classes[class_index]["name"]
    else:
        class_name = form.get("custom_class_name", "Custom Class").strip()

    # Ability scores
    scores = {}
    for ability in ["str", "dex", "con", "int", "wis", "cha"]:
        try:
            scores[ability] = int(form.get(f"score_{ability}", 10))
        except (ValueError, TypeError):
            scores[ability] = 10

    # Skills
    skill_choices = form.getlist("class_skills")
    background_skills = form.getlist("background_skills")

    # Spells
    cantrip_indices = form.getlist("cantrips")
    spell_indices = form.getlist("spells")

    # Equipment
    equipment_text = form.get("equipment_text", "")

    # Personality
    personality_traits = form.get("personality_traits", "")
    ideals = form.get("ideals", "")
    bonds = form.get("bonds", "")
    flaws = form.get("flaws", "")

    if not name:
        flash("Character name is required.", "error")
        return redirect(url_for("characters.create"))

    character = create_character(
        user_id=current_user.id,
        name=name,
        race_index=race_index,
        race_name=race_name,
        class_index=class_index,
        class_name=class_name,
        background=background,
        alignment=alignment,
        scores=scores,
        skill_choices=skill_choices,
        background_skills=background_skills,
        level=level,
        spell_indices=spell_indices,
        cantrip_indices=cantrip_indices,
        equipment_text=equipment_text,
        personality_traits=personality_traits,
        ideals=ideals,
        bonds=bonds,
        flaws=flaws,
        gender=request.form.get("gender", "").strip(),
    )

    flash(f"{character.name} created!", "success")
    return redirect(url_for("characters.sheet", character_id=character.id))


@characters_bp.route("/<int:character_id>")
@login_required
def sheet(character_id: int):
    """Display a character sheet."""
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        flash("Character not found.", "error")
        return redirect(url_for("characters.character_list"))

    # Build skill data for display
    skill_profs = {sp.skill_name: sp.proficiency_type for sp in character.skill_proficiencies}
    save_profs = {stp.ability: stp.proficient for stp in character.saving_throw_proficiencies}
    scores = character.ability_scores

    skills_display = []
    for skill_name in ALL_SKILLS:
        ability = SKILL_ABILITIES.get(skill_name, "str")
        score = scores.get(ability)
        prof_type = skill_profs.get(skill_name, "none")
        bonus = calc.skill_bonus(score, character.level, prof_type)
        skills_display.append({
            "name": skill_name,
            "ability": ability.upper(),
            "bonus": bonus,
            "proficient": prof_type != "none",
            "expert": prof_type == "expert",
        })

    saves_display = []
    for ability in ["str", "dex", "con", "int", "wis", "cha"]:
        score = scores.get(ability)
        proficient = save_profs.get(ability, False)
        bonus = calc.saving_throw_bonus(score, character.level, proficient)
        saves_display.append({
            "ability": ability.upper(),
            "bonus": bonus,
            "proficient": proficient,
        })

    # Ability modifiers
    ability_display = []
    for ability in ["str", "dex", "con", "int", "wis", "cha"]:
        score = scores.get(ability)
        mod = calc.ability_modifier(score)
        ability_display.append({
            "name": ability.upper(),
            "score": score,
            "modifier": mod,
        })

    # Spellcasting info
    spellcasting = None
    class_obj = character.classes[0] if character.classes else None
    if class_obj and class_obj.class_index in calc.SPELLCASTING_ABILITY:
        casting_ability = calc.SPELLCASTING_ABILITY[class_obj.class_index]
        casting_score = scores.get(casting_ability)
        spellcasting = {
            "ability": casting_ability.upper(),
            "save_dc": calc.spell_save_dc(casting_score, character.level),
            "attack_bonus": calc.spell_attack_bonus(casting_score, character.level),
            "cantrips": [s for s in character.known_spells if s.spell_level == 0],
            "spells": [s for s in character.known_spells if s.spell_level > 0],
            "slots": sorted(character.spell_slots, key=lambda s: s.slot_level),
        }

    # Initiative: DEX mod + any extra bonus (feats, features)
    dex_mod = calc.ability_modifier(scores.get("dex"))
    initiative_mod = dex_mod + (character.initiative_bonus or 0)

    # XP threshold for next level
    from app.blueprints.characters.api import XP_THRESHOLDS, _build_weapon_info
    xp_next = XP_THRESHOLDS.get(character.level + 1)

    # Level-up notification
    can_level_up = False
    if character.level < 20 and xp_next is not None:
        can_level_up = character.experience_points >= xp_next

    # Weapon attack info for equipment display
    weapon_info = _build_weapon_info(character)

    return render_template(
        "characters/sheet.html",
        character=character,
        abilities=ability_display,
        skills=skills_display,
        saves=saves_display,
        spellcasting=spellcasting,
        initiative_mod=initiative_mod,
        xp_next=xp_next,
        can_level_up=can_level_up,
        weapon_info=weapon_info,
        weapons=get_all_weapons(),
    )


@characters_bp.route("/schedule")
@login_required
def schedule():
    """Party timezone calculator."""
    return render_template("characters/schedule.html")


@characters_bp.route("/<int:character_id>/delete", methods=["POST"])
@login_required
def delete(character_id: int):
    """Delete a character."""
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        flash("Character not found.", "error")
        return redirect(url_for("characters.character_list"))

    name = character.name
    db.session.delete(character)
    db.session.commit()
    flash(f"{name} has been deleted.", "info")
    return redirect(url_for("characters.character_list"))


@characters_bp.route("/<int:character_id>/edit", methods=["GET", "POST"])
@login_required
def edit(character_id: int):
    """Edit a character's core stats."""
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        flash("Character not found.", "error")
        return redirect(url_for("characters.character_list"))

    if request.method == "POST":
        return _handle_edit(character)

    skill_profs = {sp.skill_name: sp.proficiency_type for sp in character.skill_proficiencies}
    save_profs = {stp.ability: stp.proficient for stp in character.saving_throw_proficiencies}

    return render_template(
        "characters/edit.html",
        character=character,
        skill_profs=skill_profs,
        save_profs=save_profs,
        all_skills=ALL_SKILLS,
        skill_abilities=SKILL_ABILITIES,
    )


def _handle_edit(character: Character):
    """Process the character edit form submission.

    Args:
        character: The Character ORM object to update (ownership already verified).

    Returns:
        A redirect response.
    """
    form = request.form

    # Identity fields
    name = form.get("name", "").strip()
    if not name:
        flash("Character name is required.", "error")
        return redirect(url_for("characters.edit", character_id=character.id))
    character.name = name[:100]
    character.race = form.get("race", "").strip()[:50] or character.race
    character.race_index = form.get("race_index", "").strip()[:50] or None
    character.subrace = form.get("subrace", "").strip()[:50] or None
    character.background = form.get("background", "").strip()[:50] or "Custom"
    character.alignment = form.get("alignment", "")[:50]
    character.gender = form.get("gender", "").strip()[:30]

    # Level and derived stats
    level = _clamp(form.get("level"), 1, 20, character.level)
    character.level = level
    character.proficiency_bonus = calc.proficiency_bonus(level)
    character.hit_dice_total = level
    character.hit_dice_remaining = min(character.hit_dice_remaining, level)

    # Combat stats
    character.max_hp = _clamp(form.get("max_hp"), 1, 9999, character.max_hp)
    character.current_hp = min(character.current_hp, character.max_hp)
    character.armor_class = _clamp(form.get("armor_class"), 1, 30, character.armor_class)
    character.speed = _clamp(form.get("speed"), 0, 120, character.speed)
    character.initiative_bonus = _clamp(form.get("initiative_bonus"), -10, 20, character.initiative_bonus)

    # Ability scores
    scores = character.ability_scores
    if scores:
        scores.strength = _clamp(form.get("score_str"), 1, 30, scores.strength)
        scores.dexterity = _clamp(form.get("score_dex"), 1, 30, scores.dexterity)
        scores.constitution = _clamp(form.get("score_con"), 1, 30, scores.constitution)
        scores.intelligence = _clamp(form.get("score_int"), 1, 30, scores.intelligence)
        scores.wisdom = _clamp(form.get("score_wis"), 1, 30, scores.wisdom)
        scores.charisma = _clamp(form.get("score_cha"), 1, 30, scores.charisma)

    # Character class (first class only)
    if character.classes:
        cls = character.classes[0]
        cls_name = form.get("class_name", "").strip()
        if cls_name:
            cls.class_name = cls_name[:50]
        cls.class_index = form.get("class_index", "").strip()[:50] or None
        cls.subclass = form.get("subclass", "").strip()[:50] or None
        cls.level = level
        cls.hit_die = _clamp(form.get("hit_die"), 4, 12, cls.hit_die)

    # Skill proficiencies — replace all
    for sp in list(character.skill_proficiencies):
        db.session.delete(sp)
    for skill in ALL_SKILLS:
        field_name = "skill_" + skill.replace(" ", "_").lower()
        value = form.get(field_name, "none")
        if value in ("proficient", "expert"):
            db.session.add(SkillProficiency(
                character_id=character.id,
                skill_name=skill,
                proficiency_type=value,
            ))

    # Saving throw proficiencies — replace all
    for stp in list(character.saving_throw_proficiencies):
        db.session.delete(stp)
    for ability in ("str", "dex", "con", "int", "wis", "cha"):
        if form.get(f"save_{ability}"):
            db.session.add(SavingThrowProficiency(
                character_id=character.id,
                ability=ability,
                proficient=True,
            ))

    db.session.commit()
    flash(f"{character.name} updated!", "success")
    return redirect(url_for("characters.sheet", character_id=character.id))


# --- Level Up ---

ABILITY_MAP = {
    "str": "strength",
    "dex": "dexterity",
    "con": "constitution",
    "int": "intelligence",
    "wis": "wisdom",
    "cha": "charisma",
}


@characters_bp.route("/<int:character_id>/level-up", methods=["GET"])
@login_required
def level_up(character_id: int):
    """Display the level-up wizard for a character."""
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        flash("Character not found.", "error")
        return redirect(url_for("characters.character_list"))

    if character.level >= 20:
        flash("This character is already at maximum level.", "error")
        return redirect(url_for("characters.sheet", character_id=character.id))

    cls = character.classes[0] if character.classes else None
    class_index = cls.class_index if cls else ""
    hit_die = cls.hit_die if cls else 8
    new_level = character.level + 1

    con_score = character.ability_scores.constitution if character.ability_scores else 10
    con_mod = calc.ability_modifier(con_score)

    avg_hp = hit_die // 2 + 1 + con_mod

    if class_index == "fighter":
        is_asi_level = new_level in calc.FIGHTER_ASI_LEVELS
    else:
        is_asi_level = new_level in calc.ASI_LEVELS

    old_names = {f["name"] for f in get_features_for_class(class_index, character.level)}
    new_features_list = get_features_for_class(class_index, new_level)
    gained_features = [f for f in new_features_list if f["name"] not in old_names]

    old_prof = calc.proficiency_bonus(character.level)
    new_prof = calc.proficiency_bonus(new_level)
    prof_changed = old_prof != new_prof

    old_slots = calc.spell_slots_for_level(class_index, character.level)
    new_slots = calc.spell_slots_for_level(class_index, new_level)
    slot_changes = {}
    all_levels = set(old_slots.keys()) | set(new_slots.keys())
    for lvl in sorted(all_levels):
        old_count = old_slots.get(lvl, 0)
        new_count = new_slots.get(lvl, 0)
        if old_count != new_count:
            slot_changes[lvl] = {"old": old_count, "new": new_count}

    scores = character.ability_scores.as_dict() if character.ability_scores else {}

    return render_template(
        "characters/level_up.html",
        character=character,
        new_level=new_level,
        hit_die=hit_die,
        con_mod=con_mod,
        avg_hp=avg_hp,
        is_asi_level=is_asi_level,
        gained_features=gained_features,
        prof_changed=prof_changed,
        old_prof=old_prof,
        new_prof=new_prof,
        slot_changes=slot_changes,
        scores=scores,
    )


@characters_bp.route("/<int:character_id>/level-up", methods=["POST"])
@login_required
def level_up_post(character_id: int):
    """Process the level-up form submission."""
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        flash("Character not found.", "error")
        return redirect(url_for("characters.character_list"))

    if character.level >= 20:
        flash("This character is already at maximum level.", "error")
        return redirect(url_for("characters.sheet", character_id=character.id))

    cls = character.classes[0] if character.classes else None
    class_index = cls.class_index if cls else ""
    hit_die = cls.hit_die if cls else 8
    new_level = character.level + 1

    con_score = character.ability_scores.constitution if character.ability_scores else 10
    con_mod = calc.ability_modifier(con_score)

    # HP gain
    hp_choice = request.form.get("hp_choice", "average")
    if hp_choice == "roll":
        try:
            hp_roll_value = int(request.form.get("hp_roll_value", 0))
        except (ValueError, TypeError):
            hp_roll_value = 0
        hp_gain = max(1, hp_roll_value) + con_mod
    else:
        hp_gain = hit_die // 2 + 1 + con_mod
    hp_gain = max(1, hp_gain)

    # Apply level-up changes
    character.level = new_level
    if cls:
        cls.level = new_level
    character.max_hp += hp_gain
    character.current_hp = character.max_hp
    character.proficiency_bonus = calc.proficiency_bonus(new_level)
    character.hit_dice_total = new_level
    character.hit_dice_remaining = new_level

    # ASI
    if class_index == "fighter":
        is_asi_level = new_level in calc.FIGHTER_ASI_LEVELS
    else:
        is_asi_level = new_level in calc.ASI_LEVELS

    if is_asi_level and character.ability_scores:
        asi_mode = request.form.get("asi_mode", "plus2")
        if asi_mode == "plus2":
            asi_ability_1 = request.form.get("asi_ability_1")
            if asi_ability_1 and asi_ability_1 in ABILITY_MAP:
                long_name = ABILITY_MAP[asi_ability_1]
                current_val = getattr(character.ability_scores, long_name, 10)
                setattr(character.ability_scores, long_name, min(20, current_val + 2))
        elif asi_mode == "plus1plus1":
            asi_ability_1 = request.form.get("asi_ability_1_a")
            asi_ability_2 = request.form.get("asi_ability_2")
            if asi_ability_1 and asi_ability_1 in ABILITY_MAP:
                long_name = ABILITY_MAP[asi_ability_1]
                current_val = getattr(character.ability_scores, long_name, 10)
                setattr(character.ability_scores, long_name, min(20, current_val + 1))
            if asi_ability_2 and asi_ability_2 in ABILITY_MAP:
                long_name = ABILITY_MAP[asi_ability_2]
                current_val = getattr(character.ability_scores, long_name, 10)
                setattr(character.ability_scores, long_name, min(20, current_val + 1))

    # New features
    old_names = {f["name"] for f in get_features_for_class(class_index, character.level - 1)}
    new_features_list = get_features_for_class(class_index, new_level)
    gained_features = [f for f in new_features_list if f["name"] not in old_names]
    for feat in gained_features:
        desc_list = feat.get("desc", [])
        description = "\n".join(desc_list) if desc_list else ""
        db.session.add(ClassFeature(
            character_id=character.id,
            feature_name=feat["name"],
            description=description,
            source=cls.class_name if cls else "",
        ))

    # Spell slots — delete and recreate
    for slot in list(character.spell_slots):
        db.session.delete(slot)
    new_slots = calc.spell_slots_for_level(class_index, new_level)
    for slot_level, count in new_slots.items():
        db.session.add(SpellSlot(
            character_id=character.id,
            slot_level=slot_level,
            total=count,
            used=0,
        ))

    db.session.commit()
    flash(f"{character.name} is now level {new_level}!", "success")
    return redirect(url_for("characters.sheet", character_id=character.id))


# --- Export / Import ---


SHEETFORGE_VERSION = "0.1.0"


@characters_bp.route("/<int:character_id>/export")
@login_required
def export(character_id: int):
    """Export a character as a JSON file download."""
    character = db.session.get(Character, character_id)
    if not character or character.user_id != current_user.id:
        flash("Character not found.", "error")
        return redirect(url_for("characters.character_list"))

    data = _serialize_character(character)
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")

    safe_name = "".join(
        c if c.isalnum() or c in " _-" else "_" for c in character.name
    ).strip()
    filename = f"{safe_name}.json"

    return Response(
        json_bytes,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _serialize_character(c: Character) -> dict:
    """Serialize a character and all related data for export.

    Args:
        c: The Character ORM object.

    Returns:
        A dict matching the Sheetforge export schema.
    """
    scores = c.ability_scores
    return {
        "sheetforge_version": SHEETFORGE_VERSION,
        "character": {
            "name": c.name,
            "race": c.race,
            "race_index": c.race_index or "",
            "subrace": c.subrace or "",
            "background": c.background,
            "alignment": c.alignment or "",
            "gender": c.gender or "",
            "level": c.level,
            "experience_points": c.experience_points or 0,
            "max_hp": c.max_hp,
            "armor_class": c.armor_class,
            "initiative_bonus": c.initiative_bonus,
            "speed": c.speed,
            "proficiency_bonus": c.proficiency_bonus,
            "hit_dice_total": c.hit_dice_total,
            "hit_dice_remaining": c.hit_dice_total,  # reset to full
            "personality_traits": c.personality_traits or "",
            "ideals": c.ideals or "",
            "bonds": c.bonds or "",
            "flaws": c.flaws or "",
            "backstory": c.backstory or "",
            "notes": c.notes or "",
            "portrait_url": c.portrait_url or "",
        },
        "ability_scores": scores.as_dict() if scores else {
            "str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10,
        },
        "classes": [
            {
                "class_name": cls.class_name,
                "class_index": cls.class_index or "",
                "subclass": cls.subclass or "",
                "level": cls.level,
                "hit_die": cls.hit_die,
            }
            for cls in c.classes
        ],
        "skill_proficiencies": [
            {"skill_name": sp.skill_name, "proficiency_type": sp.proficiency_type}
            for sp in c.skill_proficiencies
        ],
        "saving_throws": [
            {"ability": st.ability, "proficient": st.proficient}
            for st in c.saving_throw_proficiencies
        ],
        "spell_slots": [
            {"slot_level": ss.slot_level, "total": ss.total, "used": 0}
            for ss in c.spell_slots
        ],
        "known_spells": [
            {
                "spell_name": ks.spell_name,
                "spell_index": ks.spell_index or "",
                "spell_level": ks.spell_level,
                "prepared": ks.prepared,
                "source": ks.source or "class",
            }
            for ks in c.known_spells
        ],
        "inventory": [
            {
                "name": item.name,
                "quantity": item.quantity,
                "weight": item.weight,
                "equipped": item.equipped,
                "attunement": item.attunement,
                "description": item.description or "",
                "weapon_index": item.weapon_index or "",
                "magic_bonus": item.magic_bonus or 0,
            }
            for item in c.inventory
        ],
        "features": [
            {
                "feature_name": f.feature_name,
                "description": f.description or "",
                "source": f.source or "",
                "uses_total": f.uses_total,
                "uses_remaining": f.uses_total,  # reset to full
                "recharge_on": f.recharge_on,
            }
            for f in c.features
        ],
    }


@characters_bp.route("/import", methods=["POST"])
@login_required
def import_character():
    """Import a character from a JSON file upload."""
    file = request.files.get("file")
    if not file or not file.filename:
        flash("No file selected.", "error")
        return redirect(url_for("characters.character_list"))

    try:
        data = json.load(file)
    except (json.JSONDecodeError, UnicodeDecodeError):
        flash("Invalid JSON file.", "error")
        return redirect(url_for("characters.character_list"))

    error = _validate_import(data)
    if error:
        flash(error, "error")
        return redirect(url_for("characters.character_list"))

    character = _create_from_import(data, current_user.id)
    flash(f"{character.name} imported!", "success")
    return redirect(url_for("characters.sheet", character_id=character.id))


def _validate_import(data: dict) -> str | None:
    """Validate import data structure. Returns error message or None.

    Args:
        data: The parsed JSON dict.

    Returns:
        An error string if validation fails, None if valid.
    """
    if not isinstance(data, dict):
        return "Invalid file format."
    if "sheetforge_version" not in data:
        return "Not a Sheetforge export file (missing version)."
    char = data.get("character")
    if not isinstance(char, dict):
        return "Missing character data."
    if not char.get("name", "").strip():
        return "Character name is required."
    if not char.get("race", "").strip():
        return "Character race is required."
    level = char.get("level", 1)
    if not isinstance(level, int) or level < 1:
        return "Character level must be at least 1."
    if not isinstance(data.get("ability_scores"), dict):
        return "Missing ability scores."
    classes = data.get("classes")
    if not isinstance(classes, list) or len(classes) < 1:
        return "At least one class is required."
    return None


def _clamp(value, lo, hi, default):
    """Clamp a numeric value to a range with a fallback default.

    Args:
        value: The value to clamp (may be non-numeric).
        lo: Minimum allowed value.
        hi: Maximum allowed value.
        default: Fallback if value is not a valid number.

    Returns:
        The clamped integer.
    """
    try:
        return max(lo, min(hi, int(value)))
    except (ValueError, TypeError):
        return default


def _create_from_import(data: dict, user_id: int) -> Character:
    """Create a Character and all related objects from import data.

    Args:
        data: Validated Sheetforge export dict.
        user_id: The ID of the importing user.

    Returns:
        The newly created Character object.
    """
    char = data["character"]
    level = _clamp(char.get("level"), 1, 20, 1)
    max_hp = _clamp(char.get("max_hp"), 1, 999, 10)
    hit_dice_total = _clamp(char.get("hit_dice_total"), 1, 20, level)

    character = Character(
        user_id=user_id,
        name=char["name"].strip()[:100],
        race=char["race"].strip()[:50],
        race_index=char.get("race_index", "")[:50] or None,
        subrace=char.get("subrace", "")[:50] or None,
        background=char.get("background", "Custom").strip()[:50] or "Custom",
        alignment=char.get("alignment", "")[:50],
        gender=char.get("gender", "")[:30],
        level=level,
        experience_points=_clamp(char.get("experience_points"), 0, 999999, 0),
        max_hp=max_hp,
        current_hp=max_hp,  # fresh import at full health
        temp_hp=0,
        hit_dice_total=hit_dice_total,
        hit_dice_remaining=hit_dice_total,
        death_save_successes=0,
        death_save_failures=0,
        inspiration=False,
        armor_class=_clamp(char.get("armor_class"), 1, 30, 10),
        initiative_bonus=_clamp(char.get("initiative_bonus"), -10, 20, 0),
        speed=_clamp(char.get("speed"), 0, 120, 30),
        proficiency_bonus=_clamp(char.get("proficiency_bonus"), 2, 6, 2),
        personality_traits=char.get("personality_traits", ""),
        ideals=char.get("ideals", ""),
        bonds=char.get("bonds", ""),
        flaws=char.get("flaws", ""),
        backstory=char.get("backstory", ""),
        notes=char.get("notes", ""),
        portrait_url=char.get("portrait_url", "")[:500],
    )
    db.session.add(character)
    db.session.flush()  # get character.id for foreign keys

    # Ability Scores
    scores_data = data.get("ability_scores", {})
    ability_scores = AbilityScores(
        character_id=character.id,
        strength=_clamp(scores_data.get("str"), 1, 30, 10),
        dexterity=_clamp(scores_data.get("dex"), 1, 30, 10),
        constitution=_clamp(scores_data.get("con"), 1, 30, 10),
        intelligence=_clamp(scores_data.get("int"), 1, 30, 10),
        wisdom=_clamp(scores_data.get("wis"), 1, 30, 10),
        charisma=_clamp(scores_data.get("cha"), 1, 30, 10),
    )
    db.session.add(ability_scores)

    # Classes
    for cls_data in data.get("classes", []):
        if not cls_data.get("class_name"):
            continue
        db.session.add(CharacterClass(
            character_id=character.id,
            class_name=cls_data["class_name"][:50],
            class_index=cls_data.get("class_index", "")[:50] or None,
            subclass=cls_data.get("subclass", "")[:50] or None,
            level=_clamp(cls_data.get("level"), 1, 20, 1),
            hit_die=_clamp(cls_data.get("hit_die"), 4, 12, 8),
        ))

    # Skill Proficiencies
    for sp_data in data.get("skill_proficiencies", []):
        if not sp_data.get("skill_name"):
            continue
        prof_type = sp_data.get("proficiency_type", "proficient")
        if prof_type not in ("none", "proficient", "expert"):
            prof_type = "proficient"
        db.session.add(SkillProficiency(
            character_id=character.id,
            skill_name=sp_data["skill_name"][:30],
            proficiency_type=prof_type,
        ))

    # Saving Throws
    valid_abilities = {"str", "dex", "con", "int", "wis", "cha"}
    for st_data in data.get("saving_throws", []):
        ability = st_data.get("ability", "").lower()
        if ability not in valid_abilities:
            continue
        db.session.add(SavingThrowProficiency(
            character_id=character.id,
            ability=ability,
            proficient=bool(st_data.get("proficient", False)),
        ))

    # Spell Slots
    for ss_data in data.get("spell_slots", []):
        slot_level = _clamp(ss_data.get("slot_level"), 1, 9, None)
        if slot_level is None:
            continue
        db.session.add(SpellSlot(
            character_id=character.id,
            slot_level=slot_level,
            total=_clamp(ss_data.get("total"), 0, 10, 0),
            used=0,  # fresh import
        ))

    # Known Spells
    for ks_data in data.get("known_spells", []):
        if not ks_data.get("spell_name"):
            continue
        source = ks_data.get("source", "class")
        if source not in ("class", "race", "feat"):
            source = "class"
        db.session.add(KnownSpell(
            character_id=character.id,
            spell_name=ks_data["spell_name"][:100],
            spell_index=ks_data.get("spell_index", "")[:100] or None,
            spell_level=_clamp(ks_data.get("spell_level"), 0, 9, 0),
            prepared=bool(ks_data.get("prepared", True)),
            source=source,
        ))

    # Inventory
    for item_data in data.get("inventory", []):
        if not item_data.get("name"):
            continue
        db.session.add(InventoryItem(
            character_id=character.id,
            name=item_data["name"][:100],
            quantity=_clamp(item_data.get("quantity"), 0, 9999, 1),
            weight=max(0.0, float(item_data.get("weight", 0.0) or 0.0)),
            equipped=bool(item_data.get("equipped", False)),
            attunement=bool(item_data.get("attunement", False)),
            description=item_data.get("description", ""),
            weapon_index=item_data.get("weapon_index", "")[:50] or None,
            magic_bonus=max(0, min(3, int(item_data.get("magic_bonus", 0) or 0))),
        ))

    # Features
    for f_data in data.get("features", []):
        if not f_data.get("feature_name"):
            continue
        uses_total = f_data.get("uses_total")
        if uses_total is not None:
            uses_total = _clamp(uses_total, 0, 99, None)
        recharge = f_data.get("recharge_on")
        if recharge not in (None, "short_rest", "long_rest", "dawn"):
            recharge = None
        db.session.add(ClassFeature(
            character_id=character.id,
            feature_name=f_data["feature_name"][:100],
            description=f_data.get("description", ""),
            source=f_data.get("source", "")[:50],
            uses_total=uses_total,
            uses_remaining=uses_total,  # start fully charged
            recharge_on=recharge,
        ))

    db.session.commit()
    return character
