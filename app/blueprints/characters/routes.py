import json

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.characters import characters_bp
from app.extensions import db
from app.models.character import Character
from app.services import calculations as calc
from app.services.character_creator import create_character
from app.srd import (
    ALL_SKILLS,
    SKILL_ABILITIES,
    get_class,
    get_class_skill_choices,
    get_classes,
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
    initiative_mod = dex_mod + character.initiative_bonus

    # XP threshold for next level
    from app.blueprints.characters.api import XP_THRESHOLDS
    xp_next = XP_THRESHOLDS.get(character.level + 1)

    return render_template(
        "characters/sheet.html",
        character=character,
        abilities=ability_display,
        skills=skills_display,
        saves=saves_display,
        spellcasting=spellcasting,
        initiative_mod=initiative_mod,
        xp_next=xp_next,
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
