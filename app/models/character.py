from app.extensions import db


class Character(db.Model):
    """A D&D 5e player character."""

    __tablename__ = "characters"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    race = db.Column(db.String(50), nullable=False)
    race_index = db.Column(db.String(50))
    subrace = db.Column(db.String(50))
    background = db.Column(db.String(50), nullable=False)
    alignment = db.Column(db.String(50), default="")
    gender = db.Column(db.String(30), default="")
    experience_points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)

    # Session-mutable combat stats
    max_hp = db.Column(db.Integer, nullable=False)
    current_hp = db.Column(db.Integer, nullable=False)
    temp_hp = db.Column(db.Integer, default=0)
    hit_dice_total = db.Column(db.Integer, default=1)
    hit_dice_remaining = db.Column(db.Integer, default=1)
    death_save_successes = db.Column(db.Integer, default=0)
    death_save_failures = db.Column(db.Integer, default=0)
    inspiration = db.Column(db.Boolean, default=False)

    # Derived / stored combat stats
    armor_class = db.Column(db.Integer, default=10)
    initiative_bonus = db.Column(db.Integer, default=0)  # Extra initiative beyond DEX mod (feats, features)
    speed = db.Column(db.Integer, default=30)
    proficiency_bonus = db.Column(db.Integer, default=2)

    # Personality / notes
    personality_traits = db.Column(db.Text, default="")
    ideals = db.Column(db.Text, default="")
    bonds = db.Column(db.Text, default="")
    flaws = db.Column(db.Text, default="")
    backstory = db.Column(db.Text, default="")
    notes = db.Column(db.Text, default="")
    portrait_url = db.Column(db.String(500), default="")

    # Relationships
    ability_scores = db.relationship(
        "AbilityScores", backref="character", uselist=False, cascade="all, delete-orphan"
    )
    classes = db.relationship(
        "CharacterClass", backref="character", cascade="all, delete-orphan"
    )
    skill_proficiencies = db.relationship(
        "SkillProficiency", backref="character", cascade="all, delete-orphan"
    )
    saving_throw_proficiencies = db.relationship(
        "SavingThrowProficiency", backref="character", cascade="all, delete-orphan"
    )
    spell_slots = db.relationship(
        "SpellSlot", backref="character", cascade="all, delete-orphan"
    )
    known_spells = db.relationship(
        "KnownSpell", backref="character", cascade="all, delete-orphan"
    )
    inventory = db.relationship(
        "InventoryItem", backref="character", cascade="all, delete-orphan"
    )
    features = db.relationship(
        "ClassFeature", backref="character", cascade="all, delete-orphan"
    )

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def __repr__(self) -> str:
        return f"<Character {self.name} (Level {self.level})>"


class AbilityScores(db.Model):
    """Six ability scores for a character (one row per character)."""

    __tablename__ = "ability_scores"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False, unique=True
    )

    strength = db.Column(db.Integer, nullable=False, default=10)
    dexterity = db.Column(db.Integer, nullable=False, default=10)
    constitution = db.Column(db.Integer, nullable=False, default=10)
    intelligence = db.Column(db.Integer, nullable=False, default=10)
    wisdom = db.Column(db.Integer, nullable=False, default=10)
    charisma = db.Column(db.Integer, nullable=False, default=10)

    def as_dict(self) -> dict[str, int]:
        """Return scores as a dictionary."""
        return {
            "str": self.strength,
            "dex": self.dexterity,
            "con": self.constitution,
            "int": self.intelligence,
            "wis": self.wisdom,
            "cha": self.charisma,
        }

    def get(self, ability: str) -> int:
        """Get score by short name (str, dex, con, int, wis, cha)."""
        mapping = {
            "str": self.strength,
            "dex": self.dexterity,
            "con": self.constitution,
            "int": self.intelligence,
            "wis": self.wisdom,
            "cha": self.charisma,
        }
        return mapping[ability.lower()]


class CharacterClass(db.Model):
    """A class level for a character (supports multiclassing)."""

    __tablename__ = "character_classes"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    class_name = db.Column(db.String(50), nullable=False)
    class_index = db.Column(db.String(50))
    subclass = db.Column(db.String(50))
    level = db.Column(db.Integer, default=1)
    hit_die = db.Column(db.Integer, nullable=False)


class SkillProficiency(db.Model):
    """Skill proficiency for a character."""

    __tablename__ = "skill_proficiencies"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    skill_name = db.Column(db.String(30), nullable=False)
    proficiency_type = db.Column(db.String(10), default="proficient")  # none/proficient/expert


class SavingThrowProficiency(db.Model):
    """Saving throw proficiency for a character."""

    __tablename__ = "saving_throw_proficiencies"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    ability = db.Column(db.String(3), nullable=False)  # str, dex, con, int, wis, cha
    proficient = db.Column(db.Boolean, default=False)


class SpellSlot(db.Model):
    """Spell slot tracking per level."""

    __tablename__ = "spell_slots"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    slot_level = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, default=0)
    used = db.Column(db.Integer, default=0)


class KnownSpell(db.Model):
    """A spell known or prepared by a character."""

    __tablename__ = "known_spells"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    spell_name = db.Column(db.String(100), nullable=False)
    spell_index = db.Column(db.String(100))
    spell_level = db.Column(db.Integer, default=0)
    prepared = db.Column(db.Boolean, default=True)
    source = db.Column(db.String(50), default="class")  # class, race, feat


class InventoryItem(db.Model):
    """An item in a character's inventory."""

    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    weight = db.Column(db.Float, default=0.0)
    equipped = db.Column(db.Boolean, default=False)
    attunement = db.Column(db.Boolean, default=False)
    description = db.Column(db.Text, default="")


class ClassFeature(db.Model):
    """A class or race feature with optional use tracking."""

    __tablename__ = "class_features"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(
        db.Integer, db.ForeignKey("characters.id"), nullable=False
    )
    feature_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    source = db.Column(db.String(50), default="")  # class name, race, background
    uses_total = db.Column(db.Integer, nullable=True)  # None = unlimited
    uses_remaining = db.Column(db.Integer, nullable=True)
    recharge_on = db.Column(db.String(20), nullable=True)  # short_rest, long_rest, dawn
