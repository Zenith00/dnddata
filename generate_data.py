# %%
import fractions
import itertools as itt
import json
import pathlib
import re

data = json.loads(pathlib.Path("./data.json").read_text(encoding="utf-8"))
# %%


def unfold(monster, key):
    results = []
    for value in monster.get(key, []):
        if isinstance(value, str):
            results.append(value)
        elif isinstance(value, list):
            results.extend(value)
        else:
            for v in value.get(key, []):
                if isinstance(v, str):
                    if "nonmagical" in value.get("note", ""):
                        results.append(f"nm_{v}")
                elif isinstance(v, list):
                    results.extend(v)
    return results


STATS = ["str", "dex", "con", "int", "wis", "cha"]
STAT_FULLNAMES = [
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
]

STAT_SHORT_TO_FULL = {k: v for k, v in zip(STATS, STAT_FULLNAMES)}
STAT_FULL_TO_SHORT = {v: k for k, v in zip(STATS, STAT_FULLNAMES)}

stat_to_mod = lambda x: int((x - 10) / 2)

CONDITIONS = [
    "blinded",
    "charmed",
    "deafened",
    "exhaustion",
    "frightened",
    "grappled",
    "incapacitated",
    "invisible",
    "paralyzed",
    "petrified",
    "poisoned",
    "prone",
    "restrained",
    "stunned",
    "unconscious",
]
DAMAGE_TYPES = [
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
    "nm_bludgeoning",
    "nm_piercing",
    "nm_slashing",
]
# %%
MONSTER_TYPES = [
    "humanoid",
    "aberration",
    "fiend",
    "monstrosity",
    "undead",
    "dragon",
    "ooze",
    "fey",
    "elemental",
    "giant",
    "beast",
    "construct",
    "plant",
    "celestial",
]

SKILL_TO_ABILITY = {
    "athletics": "strength",
    "acrobatics": "dexterity",
    "sleight of hand": "dexterity",
    "stealth": "dexterity",
    "arcana": "intelligence",
    "history": "intelligence",
    "investigation": "intelligence",
    "nature": "intelligence",
    "religion": "intelligence",
    "animal handling": "wisdom",
    "insight": "wisdom",
    "medicine": "wisdom",
    "perception": "wisdom",
    "survival": "wisdom",
    "deception": "charisma",
    "intimidation": "charisma",
    "performance": "charisma",
    "persuasion": "charisma",
}


def damage_rating(dmg_type, monster, vulns, immunes, resists):
    if dmg_type in vulns:
        return 2
    if dmg_type in resists:
        return 0.5
    if dmg_type in immunes:
        if "Damage Absorption" in monster.get("traitTags", []):
            damage_traits = [
                trait.get("name", "").removesuffix(" Absorption").lower()
                for trait in monster.get("trait", [])
                if "Absorption" in trait.get("name", "")
            ]
            if dmg_type in damage_traits:
                return -1
        return 0
    return 1


# %%

inflated_monsters = []
for monster in data:
    try:
        monster_stats = {}
        print(monster)
        monster_stats["name"] = monster["name"]
        monster_stats |= {f"{k}SaveMod": (monster[k] - 10) // 2 for k in STATS}
        monster_stats |= {
            f"conditionImmune{k.title()}": k in monster.get("conditionImmune", [])
            for k in CONDITIONS
        }
        immunities = set(unfold(monster, "immune"))
        resistances = set(unfold(monster, "resist"))
        vulnerabilities = set(unfold(monster, "vulnerable"))

        monster_stats |= {
            f"damageImmune{k.title()}": k in immunities for k in DAMAGE_TYPES
        }
        monster_stats |= {
            f"damageResist{k.title()}": k in resistances for k in DAMAGE_TYPES
        }
        monster_stats |= {
            f"damageVulnerable{k.title()}": k in vulnerabilities for k in DAMAGE_TYPES
        }
        monster_stats |= {
            f"damageRating{k.title()}": damage_rating(
                k,
                monster=monster,
                vulns=vulnerabilities,
                immunes=immunities,
                resists=resistances,
            )
            for k in DAMAGE_TYPES
        }

        monster_stats["type"] = (
            c_type if isinstance((c_type := monster["type"]), str) else c_type["type"]
        )
        if isinstance(monster_stats["type"], dict):
            monster_stats["type"] = monster_stats["type"]["choose"][0]
        monster_stats["cr"] = (
            c_type
            if isinstance((c_type := monster.get("cr", "0")), str)
            else c_type["cr"]
        )
        monster_stats["cr_num"] = float(fractions.Fraction(monster_stats["cr"]))
        monster_stats["perception"] = int(
            monster.get("skill", {}).get("perception", 0)
        ) or (int(monster["wis"] - 10) // 2)
        monster_stats["source"] = monster["source"]
        monster_stats["named"] = monster.get("isNpc", False) or monster.get(
            "isNamedCreature", False
        )
        monster_stats["has_ranged_option"] = any(
            [
                re.search(r"range [\d\/ ]* ft", str(monster.get("action", ""))),
                re.search(
                    r"a \d*[\s-](foot|ft)[\s-](cone|line|radius|sphere|cube)",
                    str(monster.get("action", "")),
                ),
                re.search(
                    r"targets [\s\w]* creature [\s\w]*\d{2,}[\s\w]feet of",
                    str(monster.get("action", "")),
                ),
            ]
        )

        monster_stats["spellcasting"] = monster.get("spellcasting", [])
        action_entries = [
            entry
            for action in monster.get("action", [])
            for entry in action.get("entries", [])
            if entry
        ]
        entry_hit_bonuses = [
            int(x.group(1))
            for x in [
                re.search(r".*{@hit ([-+]?\d+)}", str(action_entry))
                for action_entry in action_entries
                if action_entry
            ]
            if x
        ]
        monster_stats["to_hits"] = entry_hit_bonuses
        for skill, stat in SKILL_TO_ABILITY.items():
            monster_stats[skill] = int(
                monster.get("skill", {}).get(
                    skill, stat_to_mod(monster.get(STAT_FULL_TO_SHORT[stat]))
                )
            )
        monster_stats["ac"] = (
            ac
            if isinstance((ac := monster["ac"]), int)
            else (ac[0] if isinstance(ac, list) else ac["ac"]["ac"])
        )
        monster_stats |= {
            f"induces{k.title()}Save": (
                1
                if f"{k} saving throw" in str(monster.get("action", "")).lower()
                else 0
            )
            for k in STAT_FULLNAMES
        }

        for save_bonus in monster.get("save", []):
            try:
                monster_stats[save_bonus + "SaveMod"] = int(monster["save"][save_bonus])
            except ValueError:
                continue
        inflated_monsters.append(monster_stats)

    except ValueError as e:
        print(e)


# %%
