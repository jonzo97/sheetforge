"""HTMX API endpoints for live character sheet updates.

All endpoints return HTML fragments for HTMX partial swaps.
Every endpoint verifies character ownership.
"""

from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.blueprints.characters import characters_bp
from app.extensions import db
from app.models.character import (
    Character,
    ClassFeature,
    InventoryItem,
    SpellSlot,
)
from app.services import calculations as calc
from app.services import dice as dice_service
from app.srd import SKILL_ABILITIES


def _get_owned_character(character_id: int) -> Character:
    """Fetch a character and verify ownership, or abort 403.

    Args:
        character_id: The character's database ID.

    Returns:
        The Character object.

    Raises:
        HTTPException: 404 if not found, 403 if not owned by current user.
    """
    character = db.session.get(Character, character_id)
    if not character:
        abort(404)
    if character.user_id != current_user.id:
        abort(403)
    return character


# ---------------------------------------------------------------------------
# Dice Rolling Endpoints
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/roll/skill/<skill_name>", methods=["POST"])
@login_required
def roll_skill(character_id: int, skill_name: str):
    """Roll a skill check (d20 + skill bonus).

    Args:
        character_id: Character database ID.
        skill_name: Skill name like "Athletics", "Arcana".

    Returns:
        HTML fragment with roll result.
    """
    character = _get_owned_character(character_id)
    scores = character.ability_scores
    skill_profs = {sp.skill_name: sp.proficiency_type for sp in character.skill_proficiencies}

    ability = SKILL_ABILITIES.get(skill_name, "str")
    score = scores.get(ability)
    prof_type = skill_profs.get(skill_name, "none")
    bonus = calc.skill_bonus(score, character.level, prof_type)

    sign = "+" if bonus >= 0 else ""
    expression = f"1d20{sign}{bonus}"
    result = dice_service.roll(expression)

    return render_template(
        "partials/roll_result.html",
        label=f"{skill_name} Check",
        expression=expression,
        result=result,
    )


@characters_bp.route("/<int:character_id>/roll/save/<ability>", methods=["POST"])
@login_required
def roll_save(character_id: int, ability: str):
    """Roll a saving throw (d20 + save bonus).

    Args:
        character_id: Character database ID.
        ability: Ability short name (str, dex, con, int, wis, cha).

    Returns:
        HTML fragment with roll result.
    """
    character = _get_owned_character(character_id)
    scores = character.ability_scores
    save_profs = {stp.ability: stp.proficient for stp in character.saving_throw_proficiencies}

    score = scores.get(ability.lower())
    proficient = save_profs.get(ability.lower(), False)
    bonus = calc.saving_throw_bonus(score, character.level, proficient)

    sign = "+" if bonus >= 0 else ""
    expression = f"1d20{sign}{bonus}"
    result = dice_service.roll(expression)

    return render_template(
        "partials/roll_result.html",
        label=f"{ability.upper()} Save",
        expression=expression,
        result=result,
    )


@characters_bp.route("/<int:character_id>/roll/initiative", methods=["POST"])
@login_required
def roll_initiative(character_id: int):
    """Roll initiative (d20 + DEX modifier).

    Args:
        character_id: Character database ID.

    Returns:
        HTML fragment with roll result.
    """
    character = _get_owned_character(character_id)
    dex_mod = calc.ability_modifier(character.ability_scores.get("dex"))
    total_init = dex_mod + character.initiative_bonus

    sign = "+" if total_init >= 0 else ""
    expression = f"1d20{sign}{total_init}"
    result = dice_service.roll(expression)

    return render_template(
        "partials/roll_result.html",
        label="Initiative",
        expression=expression,
        result=result,
    )


@characters_bp.route("/<int:character_id>/roll/check/<ability>", methods=["POST"])
@login_required
def roll_check(character_id: int, ability: str):
    """Roll a raw ability check (d20 + ability modifier).

    Args:
        character_id: Character database ID.
        ability: Ability short name (str, dex, con, int, wis, cha).

    Returns:
        HTML fragment with roll result.
    """
    character = _get_owned_character(character_id)
    mod = calc.ability_modifier(character.ability_scores.get(ability.lower()))

    sign = "+" if mod >= 0 else ""
    expression = f"1d20{sign}{mod}"
    result = dice_service.roll(expression)

    return render_template(
        "partials/roll_result.html",
        label=f"{ability.upper()} Check",
        expression=expression,
        result=result,
    )


@characters_bp.route("/<int:character_id>/roll/custom", methods=["POST"])
@login_required
def roll_custom(character_id: int):
    """Roll an arbitrary dice expression.

    Args:
        character_id: Character database ID.

    Returns:
        HTML fragment with roll result.
    """
    _get_owned_character(character_id)
    expression = request.form.get("expression", "1d20").strip()
    if not expression:
        expression = "1d20"

    try:
        result = dice_service.roll(expression)
    except Exception:
        return render_template(
            "partials/roll_result.html",
            label="Custom Roll",
            expression=expression,
            result=None,
            error=f"Invalid expression: {expression}",
        )

    return render_template(
        "partials/roll_result.html",
        label="Custom Roll",
        expression=expression,
        result=result,
    )


# ---------------------------------------------------------------------------
# HP Tracking
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/hp", methods=["POST"])
@login_required
def update_hp(character_id: int):
    """Update character HP (damage, heal, or set temp HP).

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered HP tracker partial.
    """
    character = _get_owned_character(character_id)
    action = request.form.get("action", "")
    try:
        amount = int(request.form.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0

    if amount < 0:
        amount = abs(amount)

    if action == "damage":
        # Temp HP absorbs damage first
        if character.temp_hp > 0:
            if amount <= character.temp_hp:
                character.temp_hp -= amount
                amount = 0
            else:
                amount -= character.temp_hp
                character.temp_hp = 0
        character.current_hp = max(0, character.current_hp - amount)
    elif action == "heal":
        character.current_hp = min(character.max_hp, character.current_hp + amount)
    elif action == "temp":
        # Temp HP replaces, doesn't stack (5e rules)
        character.temp_hp = amount

    db.session.commit()
    return render_template("partials/hp_tracker.html", character=character)


# ---------------------------------------------------------------------------
# Death Saves
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/death-save", methods=["POST"])
@login_required
def update_death_save(character_id: int):
    """Toggle or reset death saves.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered death saves partial.
    """
    character = _get_owned_character(character_id)
    save_type = request.form.get("type", "")
    action = request.form.get("action", "add")

    if action == "reset":
        character.death_save_successes = 0
        character.death_save_failures = 0
    elif save_type == "success":
        if character.death_save_successes < 3:
            character.death_save_successes += 1
    elif save_type == "failure":
        if character.death_save_failures < 3:
            character.death_save_failures += 1

    db.session.commit()
    return render_template("partials/death_saves.html", character=character)


# ---------------------------------------------------------------------------
# Inspiration
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/inspiration", methods=["POST"])
@login_required
def toggle_inspiration(character_id: int):
    """Toggle inspiration on/off.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered inspiration partial.
    """
    character = _get_owned_character(character_id)
    character.inspiration = not character.inspiration
    db.session.commit()
    return render_template("partials/inspiration.html", character=character)


# ---------------------------------------------------------------------------
# Spell Slots
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/spell-slots/<int:level>", methods=["POST"])
@login_required
def update_spell_slot(character_id: int, level: int):
    """Use or recover a spell slot.

    Args:
        character_id: Character database ID.
        level: Spell slot level (1-9).

    Returns:
        Re-rendered spell slots partial.
    """
    character = _get_owned_character(character_id)
    action = request.form.get("action", "use")

    slot = SpellSlot.query.filter_by(character_id=character_id, slot_level=level).first()
    if slot:
        if action == "use" and slot.used < slot.total:
            slot.used += 1
        elif action == "recover" and slot.used > 0:
            slot.used -= 1
        db.session.commit()

    slots = sorted(character.spell_slots, key=lambda s: s.slot_level)
    return render_template("partials/spell_slots.html", character=character, slots=slots)


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/equipment/add", methods=["POST"])
@login_required
def add_equipment(character_id: int):
    """Add an item to inventory.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered equipment list partial.
    """
    character = _get_owned_character(character_id)
    name = request.form.get("name", "").strip()
    if not name:
        return render_template("partials/equipment_list.html", character=character)

    try:
        quantity = int(request.form.get("quantity", 1))
    except (ValueError, TypeError):
        quantity = 1

    item = InventoryItem(
        character_id=character_id,
        name=name,
        quantity=max(1, quantity),
    )
    db.session.add(item)
    db.session.commit()
    return render_template("partials/equipment_list.html", character=character)


@characters_bp.route("/<int:character_id>/equipment/<int:item_id>/remove", methods=["POST"])
@login_required
def remove_equipment(character_id: int, item_id: int):
    """Remove an item from inventory.

    Args:
        character_id: Character database ID.
        item_id: Inventory item database ID.

    Returns:
        Re-rendered equipment list partial.
    """
    character = _get_owned_character(character_id)
    item = db.session.get(InventoryItem, item_id)
    if item and item.character_id == character_id:
        db.session.delete(item)
        db.session.commit()
    return render_template("partials/equipment_list.html", character=character)


@characters_bp.route("/<int:character_id>/equipment/<int:item_id>/toggle", methods=["POST"])
@login_required
def toggle_equipment(character_id: int, item_id: int):
    """Toggle equipped status of an item.

    Args:
        character_id: Character database ID.
        item_id: Inventory item database ID.

    Returns:
        Re-rendered equipment list partial.
    """
    character = _get_owned_character(character_id)
    item = db.session.get(InventoryItem, item_id)
    if item and item.character_id == character_id:
        item.equipped = not item.equipped
        db.session.commit()
    return render_template("partials/equipment_list.html", character=character)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/notes", methods=["POST"])
@login_required
def update_notes(character_id: int):
    """Save character notes.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered notes partial.
    """
    character = _get_owned_character(character_id)
    character.notes = request.form.get("notes", "")
    db.session.commit()
    return render_template("partials/notes.html", character=character)


# ---------------------------------------------------------------------------
# Feature Use Tracking
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Rest Mechanics
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/rest/short", methods=["POST"])
@login_required
def rest_short(character_id: int):
    """Take a short rest — spend hit dice to heal, recharge short-rest features.

    Args:
        character_id: Character database ID.

    Returns:
        Rest result partial with OOB swaps for affected sections.
    """
    character = _get_owned_character(character_id)

    # Parse and clamp hit dice count
    try:
        hit_dice_count = int(request.form.get("hit_dice_count", 0))
    except (ValueError, TypeError):
        hit_dice_count = 0
    hit_dice_count = max(0, min(hit_dice_count, character.hit_dice_remaining))

    # Roll hit dice for healing
    total_healing = 0
    details = []
    if hit_dice_count > 0 and character.classes:
        hit_die = character.classes[0].hit_die
        con_mod = calc.ability_modifier(character.ability_scores.get("con"))
        for i in range(hit_dice_count):
            result = dice_service.roll(f"1d{hit_die}")
            healing = max(0, result.total + con_mod)
            total_healing += healing
            sign = "+" if con_mod >= 0 else ""
            details.append(f"d{hit_die}={result.total}{sign}{con_mod} = {healing} HP")
        character.hit_dice_remaining -= hit_dice_count
        character.current_hp = min(character.max_hp, character.current_hp + total_healing)

    # Recharge short-rest features
    recharged = []
    for feat in character.features:
        if feat.recharge_on == "short_rest" and feat.uses_total is not None:
            if feat.uses_remaining < feat.uses_total:
                feat.uses_remaining = feat.uses_total
                recharged.append(feat.feature_name)

    if recharged:
        details.append(f"Recharged: {', '.join(recharged)}")

    summary_parts = []
    if hit_dice_count > 0:
        summary_parts.append(f"Spent {hit_dice_count} hit {'die' if hit_dice_count == 1 else 'dice'}, healed {total_healing} HP")
    if recharged:
        summary_parts.append(f"{len(recharged)} feature{'s' if len(recharged) != 1 else ''} recharged")
    if not summary_parts:
        summary_parts.append("Rested (nothing to recharge)")

    db.session.commit()
    return render_template(
        "partials/rest_result.html",
        character=character,
        rest_type="Short Rest",
        summary=". ".join(summary_parts) + ".",
        details=details,
    )


@characters_bp.route("/<int:character_id>/rest/long", methods=["POST"])
@login_required
def rest_long(character_id: int):
    """Take a long rest — full HP, reset slots/features/death saves, recover half hit dice.

    Args:
        character_id: Character database ID.

    Returns:
        Rest result partial with OOB swaps for all affected sections.
    """
    character = _get_owned_character(character_id)
    details = []

    # Restore HP
    hp_healed = character.max_hp - character.current_hp
    character.current_hp = character.max_hp
    character.temp_hp = 0
    if hp_healed > 0:
        details.append(f"Healed {hp_healed} HP to full")

    # Reset all spell slots
    slots_recovered = 0
    for slot in character.spell_slots:
        if slot.used > 0:
            slots_recovered += slot.used
            slot.used = 0
    if slots_recovered > 0:
        details.append(f"Recovered {slots_recovered} spell slot{'s' if slots_recovered != 1 else ''}")

    # Reset features (short_rest and long_rest)
    recharged = []
    for feat in character.features:
        if feat.recharge_on in ("short_rest", "long_rest") and feat.uses_total is not None:
            if feat.uses_remaining < feat.uses_total:
                feat.uses_remaining = feat.uses_total
                recharged.append(feat.feature_name)
    if recharged:
        details.append(f"Recharged: {', '.join(recharged)}")

    # Recover hit dice (half total, minimum 1)
    dice_to_recover = max(1, character.hit_dice_total // 2)
    old_dice = character.hit_dice_remaining
    character.hit_dice_remaining = min(
        character.hit_dice_total, character.hit_dice_remaining + dice_to_recover
    )
    dice_recovered = character.hit_dice_remaining - old_dice
    if dice_recovered > 0:
        details.append(f"Recovered {dice_recovered} hit {'die' if dice_recovered == 1 else 'dice'}")

    # Reset death saves
    character.death_save_successes = 0
    character.death_save_failures = 0

    db.session.commit()
    return render_template(
        "partials/rest_result.html",
        character=character,
        rest_type="Long Rest",
        summary="Fully rested. HP restored, spell slots and features recharged.",
        details=details,
    )


@characters_bp.route("/<int:character_id>/features/<int:feature_id>/use", methods=["POST"])
@login_required
def use_feature(character_id: int, feature_id: int):
    """Use or recover a class feature charge.

    Args:
        character_id: Character database ID.
        feature_id: ClassFeature database ID.

    Returns:
        Re-rendered feature uses partial.
    """
    character = _get_owned_character(character_id)
    feature = db.session.get(ClassFeature, feature_id)
    if not feature or feature.character_id != character_id:
        abort(404)

    action = request.form.get("action", "use")
    if feature.uses_total is not None:
        if action == "use" and feature.uses_remaining > 0:
            feature.uses_remaining -= 1
        elif action == "recover" and feature.uses_remaining < feature.uses_total:
            feature.uses_remaining += 1
        db.session.commit()

    return render_template("partials/feature_uses.html", character=character)


# ---------------------------------------------------------------------------
# XP Tracking
# ---------------------------------------------------------------------------

# 5e XP thresholds for levels 1-20
XP_THRESHOLDS = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000,
    9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000,
    15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000,
}


@characters_bp.route("/<int:character_id>/xp", methods=["POST"])
@login_required
def update_xp(character_id: int):
    """Add to or set character XP.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered XP tracker partial.
    """
    character = _get_owned_character(character_id)
    action = request.form.get("action", "add")
    try:
        amount = int(request.form.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0

    if action == "add":
        character.experience_points = max(0, character.experience_points + amount)
    elif action == "set":
        character.experience_points = max(0, amount)

    db.session.commit()

    xp_next = XP_THRESHOLDS.get(character.level + 1)
    return render_template("partials/xp_tracker.html", character=character, xp_next=xp_next)


# ---------------------------------------------------------------------------
# Backstory
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/backstory", methods=["POST"])
@login_required
def update_backstory(character_id: int):
    """Save character backstory.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered backstory partial.
    """
    character = _get_owned_character(character_id)
    character.backstory = request.form.get("backstory", "")
    db.session.commit()
    return render_template("partials/backstory.html", character=character)


# ---------------------------------------------------------------------------
# Portrait
# ---------------------------------------------------------------------------

@characters_bp.route("/<int:character_id>/portrait", methods=["POST"])
@login_required
def update_portrait(character_id: int):
    """Set character portrait URL.

    Args:
        character_id: Character database ID.

    Returns:
        Re-rendered portrait section via OOB or redirect.
    """
    character = _get_owned_character(character_id)
    url = request.form.get("portrait_url", "").strip()
    if url and not url.startswith(("https://", "http://")):
        url = ""
    character.portrait_url = url
    db.session.commit()
    return render_template("partials/portrait.html", character=character)
