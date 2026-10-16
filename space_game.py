from __future__ import annotations

from array import array
import math
import os
import random
import tempfile
import time
import tkinter as tk
import wave
from dataclasses import dataclass, field
from enum import Enum

try:
    import winsound
except ImportError:
    winsound = None

# ------------------------------------------------------------
# Starbound Diplomacy — explore solar systems, discover planets,
# befriend or fight aliens. Tkinter, no external deps.
# WASD thrust | Space brake | Shift boost | E interact/land
# G gift | T talk | F hostile act | M galaxy map | Esc quit
# ------------------------------------------------------------

W, H = 1100, 650
DT_CAP = 0.05


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


class Relation(Enum):
    ENEMY = -2
    HOSTILE = -1
    NEUTRAL = 0
    FRIENDLY = 1
    ALLY = 2


REL_NAMES = {
    Relation.ENEMY: "ENEMY",
    Relation.HOSTILE: "HOSTILE",
    Relation.NEUTRAL: "NEUTRAL",
    Relation.FRIENDLY: "FRIENDLY",
    Relation.ALLY: "ALLY",
}


@dataclass
class Moon:
    name: str
    orbit_r: float
    orbit_speed: float
    angle: float
    radius: int
    color: str


@dataclass
class CompanionStar:
    radius: int
    color: str
    glow: str
    orbit_r: float
    angle: float
    orbit_speed: float

    def pos(self) -> tuple[float, float]:
        return math.cos(self.angle) * self.orbit_r, math.sin(self.angle) * self.orbit_r


@dataclass
class Boss:
    name: str
    hp: float = 2400.0
    max_hp: float = 2400.0
    x: float = 0.0
    y: float = -250.0
    radius: float = 58.0
    elapsed: float = 0.0
    attack_timer: float = 1.2
    active: bool = True
    announced: bool = False


@dataclass
class BossProjectile:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    ttl: float = 5.0


@dataclass
class Planet:
    name: str
    orbit_r: float
    orbit_speed: float
    angle: float
    radius: int
    color: str
    moons: list[Moon] = field(default_factory=list)
    has_aliens: bool = False
    alien_species: str = ""
    discovered: bool = False
    landed: bool = False
    consumed: bool = False
    surface_nodes: dict[tuple[int, int], tuple[str, int]] = field(default_factory=dict)
    alien_surface_pos: tuple[int, int] | None = None
    black_hole: bool = False

    def pos(self) -> tuple[float, float]:
        return math.cos(self.angle) * self.orbit_r, math.sin(self.angle) * self.orbit_r


@dataclass
class SolarSystem:
    name: str
    star_color: str
    star_glow: str
    star_radius: int
    planets: list[Planet]
    bg_tint: str
    description: str
    star_event_checked: bool = False
    star_exploding: bool = False
    star_explosion_timer: float = 0.0
    black_hole: bool = False
    stellar_black_hole: bool = False
    companion_stars: list[CompanionStar] = field(default_factory=list)
    boss: Boss | None = None


@dataclass
class Alien:
    species: str
    home_planet: str
    relation: Relation = Relation.NEUTRAL
    trust: float = 0.0
    color: str = "#8cf"
    hp: float = 100.0
    active: bool = True
    in_space: bool = False
    following_player: bool = False
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0

    def step_relation(self, delta: float) -> None:
        self.trust = clamp(self.trust + delta, -100, 100)
        if self.trust <= -60:
            self.relation = Relation.ENEMY
        elif self.trust <= -25:
            self.relation = Relation.HOSTILE
        elif self.trust < 20:
            self.relation = Relation.NEUTRAL
        elif self.trust < 55:
            self.relation = Relation.FRIENDLY
        else:
            self.relation = Relation.ALLY


@dataclass
class Ship:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    angle: float = -math.pi / 2
    radius: float = 8.0
    fuel: float = 100.0
    max_fuel: float = 100.0
    hull: float = 100.0
    max_hull: float = 100.0
    thrust: float = 420.0
    boost: float = 1.65


@dataclass
class PulseShot:
    x: float
    y: float
    vx: float
    vy: float
    ttl: float = 1.5


def build_galaxy() -> list[SolarSystem]:
    systems: list[SolarSystem] = []

    systems.append(SolarSystem(
        name="Solara Prime",
        star_color="#ffe066",
        star_glow="#ffaa22",
        star_radius=76,
        bg_tint="#0a0a18",
        description="A warm yellow star with rocky inner worlds and icy moons.",
        planets=[
            Planet(name="Ember", orbit_r=120, orbit_speed=0.35, angle=0.2, radius=20, color="#c85", has_aliens=False),
            Planet(name="Verdania", orbit_r=200, orbit_speed=0.22, angle=1.1, radius=32, color="#4a8",
                   has_aliens=True, alien_species="Verdans",
                   moons=[Moon("Luna", 28, 1.2, 0.5, 9, "#bbb")]),
            Planet(name="Stormhold", orbit_r=290, orbit_speed=0.16, angle=2.4, radius=42, color="#68bdf8",
                   has_aliens=False, moons=[Moon("Io", 38, 0.9, 1.0, 12, "#dda"), Moon("Europa", 52, 0.7, 2.2, 10, "#eef")]),
            Planet(name="Ringhaven", orbit_r=400, orbit_speed=0.11, angle=4.0, radius=52, color="#d4a574",
                   has_aliens=True, alien_species="Ringers",
                   moons=[Moon("Titan", 45, 0.5, 0.8, 14, "#ca8")]),
        ],
    ))

    systems.append(SolarSystem(
        name="Crimson Reach",
        star_color="#ff6644",
        star_glow="#cc2200",
        star_radius=68,
        bg_tint="#120808",
        description="A red dwarf system — dense, ancient, and suspicious.",
        planets=[
            Planet(name="Rust", orbit_r=100, orbit_speed=0.28, angle=0.0, radius=24, color="#a44", has_aliens=True, alien_species="Rustborn"),
            Planet(name="Ashfall", orbit_r=180, orbit_speed=0.19, angle=1.5, radius=28, color="#886",
                   has_aliens=False, moons=[Moon("Cinder", 24, 1.4, 0.3, 8, "#666")]),
            Planet(name="Obsidian", orbit_r=260, orbit_speed=0.14, angle=3.1, radius=34, color="#334",
                   has_aliens=True, alien_species="Obsidians",
                   moons=[Moon("Shard", 32, 1.0, 1.8, 9, "#556"), Moon("Glass", 48, 0.8, 4.0, 8, "#778")]),
        ],
    ))

    systems.append(SolarSystem(
        name="Azure Deep",
        star_color="#88ccff",
        star_glow="#4488dd",
        star_radius=84,
        bg_tint="#060818",
        description="Blue giant light — water worlds and drifting ice moons.",
        planets=[
            Planet(name="Pelagos", orbit_r=150, orbit_speed=0.25, angle=0.8, radius=38, color="#2af",
                   has_aliens=True, alien_species="Pelagians",
                   moons=[Moon("Pearl", 35, 1.1, 0.0, 12, "#eef"), Moon("Foam", 50, 0.85, 2.5, 10, "#cde")]),
            Planet(name="Glacius", orbit_r=240, orbit_speed=0.17, angle=2.0, radius=30, color="#bdf",
                   has_aliens=False, moons=[Moon("Frost", 30, 1.3, 1.2, 10, "#fff")]),
            Planet(name="Abyss", orbit_r=330, orbit_speed=0.12, angle=3.5, radius=46, color="#036",
                   has_aliens=True, alien_species="Abyssals"),
        ],
    ))

    systems.append(SolarSystem(
        name="Violet Crown",
        star_color="#cc88ff",
        star_glow="#8844cc",
        star_radius=72,
        bg_tint="#100818",
        description="Exotic violet star — gas giants and crowded moon belts.",
        planets=[
            Planet(name="Nimbus", orbit_r=220, orbit_speed=0.13, angle=0.5, radius=58, color="#f8c878",
                   has_aliens=True, alien_species="Nimbians",
                   moons=[Moon("Alpha", 42, 0.6, 0.0, 12, "#ccc"), Moon("Beta", 58, 0.5, 1.5, 10, "#aaa"), Moon("Gamma", 72, 0.45, 3.0, 8, "#888")]),
            Planet(name="Twilight", orbit_r=320, orbit_speed=0.09, angle=2.2, radius=28, color="#808",
                   has_aliens=False, moons=[Moon("Dusk", 26, 1.5, 0.7, 10, "#606")]),
            Planet(name="Mirage", orbit_r=410, orbit_speed=0.07, angle=4.5, radius=34, color="#a6f",
                   has_aliens=True, alien_species="Mirages"),
        ],
    ))

    systems.append(SolarSystem(
        name="Ember Void",
        star_color="#ffaa44",
        star_glow="#ff6600",
        star_radius=62,
        bg_tint="#181008",
        description="Young orange star — volcanic worlds and aggressive neighbors.",
        planets=[
            Planet(name="Magma", orbit_r=110, orbit_speed=0.32, angle=1.0, radius=26, color="#f42",
                   has_aliens=True, alien_species="Magmites"),
            Planet(name="Basalt", orbit_r=195, orbit_speed=0.21, angle=2.3, radius=30, color="#543",
                   has_aliens=False, moons=[Moon("Rock", 22, 1.6, 0.0, 8, "#432")]),
            Planet(name="Forge", orbit_r=280, orbit_speed=0.15, angle=0.2, radius=38, color="#fa0",
                   has_aliens=True, alien_species="Forgers",
                   moons=[Moon("Anvil", 36, 1.0, 1.0, 12, "#876"), Moon("Spark", 50, 0.75, 2.8, 8, "#fc8")]),
        ],
    ))

    rng = random.Random(50)
    star_palette = [
        ("#ff8866", "#cc4422", "#160a0a"),
        ("#88ddff", "#4488cc", "#071018"),
        ("#ffe477", "#dd9933", "#151006"),
        ("#aaff99", "#55aa55", "#081208"),
        ("#dd99ff", "#8844bb", "#100818"),
    ]
    planet_palette = ["#4a8", "#68bdf8", "#c85", "#d4a574", "#a6f", "#bdf", "#a44", "#fa8"]
    for system_number in range(6, 100):
        star_color, star_glow, bg_tint = star_palette[rng.randrange(len(star_palette))]
        planets: list[Planet] = []
        for planet_number in range(rng.randint(3, 5)):
            has_aliens = rng.random() < 0.55
            planet_name = f"World-{system_number:02d}-{planet_number + 1}"
            moons = []
            if rng.random() < 0.45:
                moons.append(Moon(
                    name=f"Moon-{system_number:02d}-{planet_number + 1}",
                    orbit_r=rng.randint(28, 48),
                    orbit_speed=rng.uniform(0.5, 1.3),
                    angle=rng.uniform(0, math.tau),
                    radius=rng.randint(8, 12),
                    color="#bbc",
                ))
            planets.append(Planet(
                name=planet_name,
                orbit_r=115 + planet_number * 95,
                orbit_speed=rng.uniform(0.08, 0.3),
                angle=rng.uniform(0, math.tau),
                radius=rng.randint(22, 46),
                color=planet_palette[rng.randrange(len(planet_palette))],
                moons=moons,
                has_aliens=has_aliens,
                alien_species=f"People-{system_number:02d}-{planet_number + 1}" if has_aliens else "",
            ))
        systems.append(SolarSystem(
            name=f"Frontier {system_number:02d}",
            star_color=star_color,
            star_glow=star_glow,
            star_radius=rng.randint(58, 88),
            planets=planets,
            bg_tint=bg_tint,
            description="An unexplored frontier system with new worlds to discover.",
        ))

    systems.append(SolarSystem(
        name="???",
        star_color="#05020a",
        star_glow="#542474",
        star_radius=76,
        planets=[
            Planet(name="Eventide", orbit_r=150, orbit_speed=0.18, angle=0.4, radius=30,
                   color="#05020a", black_hole=True),
            Planet(name="Null", orbit_r=270, orbit_speed=0.12, angle=2.2, radius=38,
                   color="#05020a", black_hole=True),
            Planet(name="Singularity", orbit_r=390, orbit_speed=0.08, angle=4.6, radius=46,
                   color="#05020a", black_hole=True),
        ],
        bg_tint="#05030a",
        description="An uncharted system where a bright star corona surrounds a black-hole sun and black-hole planets.",
        star_event_checked=True,
        black_hole=True,
        stellar_black_hole=True,
    ))

    strange_system_specs = [
        ("Null-00", "Three planets hold perfectly still in their orbits."),
        ("Unlucky-13", "Thirteen tightly packed planets circle a blood-red star."),
        ("Answer-42", "Four planets carry exactly 42 moons between them."),
        ("Prime-97", "Seven planets orbit at prime-number distances, spinning backward."),
        ("Odd-101", "Five worlds follow odd-numbered tracks with odd-sized planets."),
        ("Mirror-1221", "Planet pairs orbit in exact mirror symmetry."),
        ("Fraction-1-137", "Four planets share almost the same fractional orbit."),
        ("Pi-3-14159", "Three planets orbit at multiples of pi times 100."),
        ("Googol-10^100", "Planet distances jump by powers of ten."),
        ("Overflow-999999", "Nine crowded planets each carry nine fast-orbiting moons."),
    ]
    prime_orbits = [173, 197, 223, 251, 307, 353, 401]
    mirror_angles = [0.0, math.pi, math.pi / 2, math.pi * 1.5]
    googol_orbits = [150, 1000, 10000, 100000]
    for anomaly_index, (system_name, description) in enumerate(strange_system_specs):
        system_number = 101 + anomaly_index
        star_color, star_glow, bg_tint = star_palette[rng.randrange(len(star_palette))]
        planets = []
        planet_count = (3, 13, 4, 7, 5, 4, 4, 3, 4, 9)[anomaly_index]
        for planet_number in range(planet_count):
            has_aliens = rng.random() < 0.55
            if anomaly_index == 0:
                orbit_r = 180 + planet_number * 140
                orbit_speed = 0.0
                angle = math.tau * planet_number / planet_count
            elif anomaly_index == 1:
                orbit_r = 115 + planet_number * 62
                orbit_speed = (-1 if planet_number % 2 else 1) * rng.uniform(0.3, 0.7)
                angle = rng.uniform(0, math.tau)
            elif anomaly_index == 3:
                orbit_r = prime_orbits[planet_number]
                orbit_speed = -rng.uniform(0.08, 0.2)
                angle = rng.uniform(0, math.tau)
            elif anomaly_index == 4:
                orbit_r = 151 + planet_number * 102
                orbit_speed = rng.uniform(0.08, 0.25)
                angle = rng.uniform(0, math.tau)
            elif anomaly_index == 5:
                orbit_r = 170 if planet_number < 2 else 320
                orbit_speed = 0.12
                angle = mirror_angles[planet_number]
            elif anomaly_index == 6:
                orbit_r = 155 + planet_number / 137
                orbit_speed = (-1 if planet_number % 2 else 1) * 0.8
                angle = 0.8 + planet_number * 0.035
            elif anomaly_index == 7:
                orbit_r = round(math.pi * 100 * (planet_number + 1))
                orbit_speed = math.pi / (8 + planet_number)
                angle = math.pi / (planet_number + 1)
            elif anomaly_index == 8:
                orbit_r = googol_orbits[planet_number]
                orbit_speed = 0.2 / (planet_number + 1)
                angle = rng.uniform(0, math.tau)
            elif anomaly_index == 9:
                orbit_r = 210 + planet_number * 4
                orbit_speed = (-1 if planet_number % 2 else 1) * rng.uniform(0.6, 1.5)
                angle = math.tau * planet_number / planet_count
            else:
                orbit_r = 140 + planet_number * 105
                orbit_speed = rng.uniform(0.08, 0.3)
                angle = rng.uniform(0, math.tau)

            if anomaly_index == 4:
                planet_radius = rng.randrange(13, 48, 2)
            else:
                planet_radius = rng.randint(22, 46)

            moon_count = 9 if anomaly_index == 9 else 0
            if anomaly_index == 2:
                moon_count = 42 // planet_count + (1 if planet_number < 42 % planet_count else 0)
            moons = [
                Moon(
                    name=f"OddMoon-{system_number}-{planet_number + 1}-{moon_number + 1}",
                    orbit_r=24 + moon_number * 3,
                    orbit_speed=rng.uniform(0.6, 1.8),
                    angle=math.tau * moon_number / max(1, moon_count),
                    radius=rng.randint(5, 10),
                    color="#bbc",
                )
                for moon_number in range(moon_count)
            ]
            planets.append(Planet(
                name=f"OddWorld-{system_number}-{planet_number + 1}",
                orbit_r=orbit_r,
                orbit_speed=orbit_speed,
                angle=angle,
                radius=planet_radius,
                color=planet_palette[rng.randrange(len(planet_palette))],
                moons=moons,
                has_aliens=has_aliens,
                alien_species=f"OddPeople-{system_number}-{planet_number + 1}" if has_aliens else "",
            ))
        systems.append(SolarSystem(
            name=system_name,
            star_color=star_color,
            star_glow=star_glow,
            star_radius=rng.randint(58, 88),
            planets=planets,
            bg_tint=bg_tint,
            description=description,
            companion_stars=[
                CompanionStar(
                    radius=rng.randint(16, 30),
                    color=star_palette[(anomaly_index + star_index + 1) % len(star_palette)][0],
                    glow=star_palette[(anomaly_index + star_index + 1) % len(star_palette)][1],
                    orbit_r=360 + star_index * 170,
                    angle=math.tau * star_index / (1 + anomaly_index % 3),
                    orbit_speed=(-1 if star_index % 2 else 1) * rng.uniform(0.04, 0.16),
                )
                for star_index in range(1 + anomaly_index % 3)
            ],
        ))

    for system_number in range(111, 116):
        star_color, star_glow, bg_tint = star_palette[system_number % len(star_palette)]
        systems.append(SolarSystem(
            name=f"Frontier {system_number}",
            star_color=star_color,
            star_glow=star_glow,
            star_radius=68 + system_number % 17,
            planets=[
                Planet(
                    name=f"FrontierWorld-{system_number}-{planet_number + 1}",
                    orbit_r=140 + planet_number * 120,
                    orbit_speed=0.1 + planet_number * 0.04,
                    angle=math.tau * planet_number / 3,
                    radius=26 + planet_number * 6,
                    color=planet_palette[(system_number + planet_number) % len(planet_palette)],
                )
                for planet_number in range(3)
            ],
            bg_tint=bg_tint,
            description="A quiet frontier system on the route to the final signal.",
        ))

    systems.append(SolarSystem(
        name="116 - THE RIFT CROWN",
        star_color="#09121f",
        star_glow="#f04455",
        star_radius=68,
        planets=[
            Planet(name="Crown Shard", orbit_r=180, orbit_speed=0.11, angle=0.8, radius=30, color="#48536d"),
            Planet(name="Rift Anchor", orbit_r=340, orbit_speed=-0.08, angle=3.4, radius=42, color="#34465c"),
        ],
        bg_tint="#080913",
        description="The final system. Defeat the Rift Warden to save the galaxy.",
        star_event_checked=True,
        boss=Boss(name="THE RIFT WARDEN"),
    ))

    return systems


def build_aliens(systems: list[SolarSystem]) -> dict[str, Alien]:
    aliens: dict[str, Alien] = {}
    colors = ["#8cf", "#f8c", "#8f8", "#fc8", "#f88", "#cff", "#c8f"]
    ci = 0
    for sys in systems:
        for pl in sys.planets:
            if pl.has_aliens and pl.alien_species:
                px, py = pl.pos()
                aliens[pl.name] = Alien(
                    species=pl.alien_species,
                    home_planet=pl.name,
                    color=colors[ci % len(colors)],
                    x=px + random.uniform(-20, 20),
                    y=py + random.uniform(-20, 20),
                )
                ci += 1
    return aliens


class SpaceGame:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Starbound Diplomacy")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(self.root, width=W, height=H, bg="#050510", highlightthickness=0)
        self.canvas.pack()

        self.systems = build_galaxy()
        self.system_idx = 0
        self.aliens = build_aliens(self.systems)
        self.ship = Ship(x=0.0, y=-80.0)
        self.projectiles: list[PulseShot] = []
        self.boss_projectiles: list[BossProjectile] = []
        self.weapon_cooldown = 0.0
        self.pressed: set[str] = set()
        self.last_t = time.perf_counter()
        self.screen = "title"
        self.show_galaxy = False
        self.galaxy_page = 0
        self.msg = ""
        self.msg_t = 0.0
        self.dialog_planet: Planet | None = None
        self.landed_planet: Planet | None = None
        self.planet_map: list[list[str]] = []
        self.planet_map_planet: Planet | None = None
        self.astronaut_pos: tuple[float, float] = (0.0, 0.0)
        self.resources = {"ore": 0, "crystal": 0, "plants": 0, "rift_shard": 0, "void_amber": 0}
        self.upgrade_levels = {"engine": 0, "hull": 0, "fuel": 0, "weapon": 0}
        self.weapon_damage = 50
        self.launch_button: tk.Button | None = None
        self.discoveries: set[str] = set()
        self.score = 0
        self.allies: set[str] = set()
        self.enemies: set[str] = set()
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.landing_t = 0.0
        self.star_pulse = 0.0
        try:
            self.music_path: str | None = self._build_music_track() if winsound is not None else None
        except (OSError, wave.Error):
            self.music_path = None
        self.music_muted = False
        self.mute_button = tk.Button(
            self.root,
            text="Mute",
            command=self._toggle_mute,
            font=("Consolas", 10, "bold"),
            width=8,
            bg="#172536",
            fg="#dff4ff",
            activebackground="#29435c",
            relief="raised",
        )
        self.mute_button.place(x=W - 100, y=10)
        if self.music_path is None:
            self.mute_button.config(state="disabled", text="No audio")
        else:
            self._play_music()

        self._bind()
        self._draw()

    def _build_music_track(self) -> str:
        sample_rate = 11025
        note_length = 1.5
        melody = (196.0, 220.0, 261.63, 293.66, 349.23, 293.66, 246.94, 220.0)
        pads = (65.41, 73.42, 55.0, 61.74)
        duration = note_length * len(melody)
        samples = array("h")
        for sample_index in range(int(sample_rate * duration)):
            t = sample_index / sample_rate
            note_index = int(t / note_length)
            note_t = t % note_length
            note = melody[note_index]
            pad = pads[int(t / 3.0) % len(pads)]
            note_envelope = min(1.0, note_t / 0.12, (note_length - note_t) / 0.28)
            loop_envelope = min(1.0, t / 0.4, (duration - t) / 0.4)
            value = (
                0.10 * math.sin(math.tau * note * t) * note_envelope
                + 0.035 * math.sin(math.tau * note * 2 * t) * note_envelope
                + 0.12 * math.sin(math.tau * pad * t)
                + 0.035 * math.sin(math.tau * pad * 1.5 * t)
            ) * loop_envelope
            samples.append(int(value * 32767))

        file_handle, path = tempfile.mkstemp(prefix="starbound_space_", suffix=".wav")
        os.close(file_handle)
        with wave.open(path, "wb") as music_file:
            music_file.setnchannels(1)
            music_file.setsampwidth(2)
            music_file.setframerate(sample_rate)
            music_file.writeframes(samples.tobytes())
        return path

    def _play_music(self) -> None:
        if winsound is not None and self.music_path is not None and not self.music_muted:
            winsound.PlaySound(
                self.music_path,
                winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP,
            )

    def _toggle_mute(self) -> None:
        self.music_muted = not self.music_muted
        if winsound is not None and self.music_muted:
            winsound.PlaySound(None, 0)
        else:
            self._play_music()
        self.mute_button.config(text="Unmute" if self.music_muted else "Mute")

    def _close_game(self) -> None:
        if winsound is not None:
            winsound.PlaySound(None, 0)
        if self.music_path is not None:
            try:
                os.remove(self.music_path)
            except OSError:
                pass
        self.root.destroy()

    def _bind(self) -> None:
        self.root.protocol("WM_DELETE_WINDOW", self._close_game)
        self.root.bind("<KeyPress>", self._on_key_down)
        self.root.bind("<KeyRelease>", self._on_key_up)
        self.root.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-1>", self._on_click)

    def _start_game(self) -> None:
        if self.screen == "title":
            self.screen = "fly"
            self.show_galaxy = False
            self.pressed.clear()
            if self.launch_button is not None:
                self.launch_button.pack_forget()
                self.launch_button.destroy()
                self.launch_button = None
            self._toast("Explore! Q fires pulse shots. Fly near planets and press E.", 5.0)
            self._check_star_collapse(self.system)
            self._draw()
            self.root.update_idletasks()

    def _restart_game(self) -> None:
        self.systems = build_galaxy()
        self.system_idx = 0
        self.aliens = build_aliens(self.systems)
        self.ship = Ship(x=0.0, y=-80.0)
        self.projectiles = []
        self.boss_projectiles = []
        self.weapon_cooldown = 0.0
        self.pressed.clear()
        self.last_t = time.perf_counter()
        self.screen = "fly"
        self.show_galaxy = False
        self.galaxy_page = 0
        self.dialog_planet = None
        self.landed_planet = None
        self.planet_map = []
        self.planet_map_planet = None
        self.astronaut_pos = (0.0, 0.0)
        self.resources = {"ore": 0, "crystal": 0, "plants": 0, "rift_shard": 0, "void_amber": 0}
        self.upgrade_levels = {"engine": 0, "hull": 0, "fuel": 0}
        self.discoveries.clear()
        self.score = 0
        self.allies.clear()
        self.enemies.clear()
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.landing_t = 0.0
        self.star_pulse = 0.0
        self.msg = ""
        self.msg_t = 0.0
        if self.launch_button is not None:
            self.launch_button.destroy()
            self.launch_button = None
        self._toast("New run started. Explore!", 3.0)
        self._check_star_collapse(self.system)
        self._draw()

    def _toast(self, text: str, duration: float = 3.0) -> None:
        self.msg = text
        self.msg_t = duration

    @property
    def system(self) -> SolarSystem:
        return self.systems[self.system_idx]

    def _on_key_down(self, e: tk.Event) -> None:
        k = e.keysym.lower()
        if k == "escape":
            self._close_game()
            return
        if self.screen == "title":
            if k in ("return", "space"):
                self._start_game()
            return
        if self.screen == "gameover":
            if k in ("return", "space"):
                self._restart_game()
            return
        if self.screen == "dialog":
            if k == "g":
                self._diplomacy_gift()
            elif k == "t":
                self._diplomacy_talk()
            elif k == "f":
                self._diplomacy_fight()
            elif k == "e" or k == "return":
                pl = self.dialog_planet
                if pl is not None:
                    self._enter_planet(pl)
                else:
                    self.screen = "fly"
                    self.dialog_planet = None
            return
        if self.screen == "surface_contact":
            if k == "g":
                self._diplomacy_gift()
            elif k == "t":
                self._diplomacy_talk()
            elif k == "f":
                self._diplomacy_fight()
            elif k in ("e", "b", "return"):
                self.screen = "planet"
                self.dialog_planet = None
            return
        if self.screen == "upgrades":
            if k in ("u", "b"):
                self.screen = "planet"
            elif k in ("1", "2", "3", "4"):
                self._purchase_upgrade({"1": "engine", "2": "hull", "3": "fuel", "4": "weapon"}[k])
            return
        if self.screen == "planet":
            if k == "u":
                self.screen = "upgrades"
                return
            if k == "e" and self.landed_planet is not None and self.landed_planet.alien_surface_pos is not None:
                ax, ay = self.landed_planet.alien_surface_pos
                px, py = self.astronaut_pos
                if abs(ax - px) + abs(ay - py) <= 1:
                    self.dialog_planet = self.landed_planet
                    self.screen = "surface_contact"
                    return
            if k in ("e", "return", "space"):
                self._launch_from_planet()
                self.screen = "fly"
                return
            if k in ("a", "d", "w", "s", "left", "right", "up", "down"):
                self._move_astronaut_on_map(k)
            return
        if self.screen != "fly":
            return
        if self.landed_planet is not None and k in ("e", "return", "space", "w", "up"):
            self._open_planet_map()
            return
        if self.show_galaxy:
            if k in ("bracketright", "pagedown"):
                self.galaxy_page = min(self.galaxy_page + 1, (len(self.systems) - 1) // 10)
                return
            if k in ("bracketleft", "pageup"):
                self.galaxy_page = max(0, self.galaxy_page - 1)
                return
            if k.isdigit():
                page_slot = 9 if k == "0" else int(k) - 1
                idx = self.galaxy_page * 10 + page_slot
                if idx < len(self.systems):
                    self._warp_to_system(idx)
                    self.show_galaxy = False
                return
        if k == "m":
            self.show_galaxy = not self.show_galaxy
        elif k in ("w", "a", "s", "d", "up", "down", "left", "right", "shift_l", "shift_r"):
            self.pressed.add("shift" if "shift" in k else k)
        elif k == "space":
            self.pressed.add("brake")
        elif k == "q" and not self.show_galaxy:
            self._fire_weapon()
        elif k == "e":
            self._try_interact()
        elif k.isdigit() and k != "0":
            idx = int(k) - 1
            if idx < len(self.systems):
                self._warp_to_system(idx)

    def _on_key_up(self, e: tk.Event) -> None:
        k = e.keysym.lower()
        if k == "space":
            self.pressed.discard("brake")
        elif k in ("shift_l", "shift_r"):
            self.pressed.discard("shift")
        else:
            self.pressed.discard(k)

    def _on_click(self, e: tk.Event) -> None:
        if self.screen == "title":
            self._start_game()
            return
        if self.show_galaxy:
            mx, my = e.x, e.y
            bx, by, bw, bh = W // 2 - 220, 80, 440, 420
            if not (bx <= mx <= bx + bw and by <= my <= by + bh):
                return
            if by + 380 <= my <= by + 414:
                if mx < W // 2:
                    self.galaxy_page = max(0, self.galaxy_page - 1)
                else:
                    self.galaxy_page = min(self.galaxy_page + 1, (len(self.systems) - 1) // 10)
                return
            row_top = by + 48
            row_h = 32
            page_slot = int((my - row_top) / row_h)
            idx = self.galaxy_page * 10 + page_slot
            if 0 <= page_slot < 10 and idx < len(self.systems):
                self._warp_to_system(idx)
                self.show_galaxy = False

    def _warp_to_system(self, idx: int) -> None:
        if idx == self.system_idx:
            self._toast("Already in this system.")
            return
        self.system_idx = idx
        self.ship.x, self.ship.y = 0.0, -90.0
        self.ship.vx = self.ship.vy = 0.0
        self.projectiles.clear()
        self.boss_projectiles.clear()
        self._toast(f"Warped to {self.system.name}", 2.5)
        self._check_star_collapse(self.system)
        for pl in self.system.planets:
            if pl.has_aliens:
                al = self.aliens.get(pl.name)
                if al:
                    px, py = pl.pos()
                    al.x, al.y = px + 30, py
                    al.vx = al.vy = 0.0
        self._position_followers_near_ship()
        self._show_boss_alert()

    def _system_edge_radius(self) -> float:
        outer_planet = max(
            (pl.orbit_r + pl.radius for pl in self.system.planets),
            default=float(self.system.star_radius),
        )
        outer_star = max(
            (star.orbit_r + star.radius for star in self.system.companion_stars),
            default=0.0,
        )
        return max(outer_planet, outer_star) + 220

    def _travel_to_next_system(self) -> None:
        direction_len = math.hypot(self.ship.x, self.ship.y)
        if direction_len == 0:
            direction_x, direction_y = 0.0, -1.0
        else:
            direction_x = self.ship.x / direction_len
            direction_y = self.ship.y / direction_len

        self.system_idx = (self.system_idx + 1) % len(self.systems)
        self.projectiles.clear()
        self.boss_projectiles.clear()
        entry_radius = self._system_edge_radius()
        self.ship.x = -direction_x * entry_radius
        self.ship.y = -direction_y * entry_radius
        self.cam_x = self.ship.x
        self.cam_y = self.ship.y
        self.show_galaxy = False
        self._check_star_collapse(self.system)
        for pl in self.system.planets:
            if pl.has_aliens and pl.name in self.aliens:
                al = self.aliens[pl.name]
                if not al.in_space:
                    px, py = pl.pos()
                    al.x, al.y = px + 30, py
                    al.vx = al.vy = 0.0
        self._position_followers_near_ship()
        if not self._show_boss_alert():
            self._toast(f"Entered {self.system.name}. Keep flying to explore.", 3.0)

    def _show_boss_alert(self) -> bool:
        boss = self.system.boss
        if boss is None or not boss.active or boss.announced:
            return False
        boss.announced = True
        self._toast(f"BOSS ALERT: {boss.name}! Q to fire. Keep moving!", 5.0)
        return True

    def _position_followers_near_ship(self) -> None:
        followers = sorted(
            (alien for alien in self.aliens.values() if alien.following_player and alien.active),
            key=lambda alien: alien.species,
        )
        for index, alien in enumerate(followers):
            angle = math.tau * index / max(1, len(followers))
            distance = 70 + 24 * (index // 8)
            alien.x = self.ship.x + math.cos(angle) * distance
            alien.y = self.ship.y + math.sin(angle) * distance
            alien.vx = self.ship.vx
            alien.vy = self.ship.vy

    def _check_star_collapse(self, system: SolarSystem) -> None:
        if system.star_event_checked or system.black_hole:
            system.star_event_checked = True
            return
        system.star_event_checked = True
        if random.random() < 0.1:
            system.star_exploding = True
            system.star_explosion_timer = 2.5
            self._toast(f"WARNING: {system.name}'s star is exploding!", 3.0)

    def _update_star_event(self, dt: float) -> None:
        system = self.system
        if not system.star_exploding:
            return
        system.star_explosion_timer -= dt
        if system.star_explosion_timer <= 0:
            system.star_explosion_timer = 0.0
            system.star_exploding = False
            system.black_hole = True
            self._toast("The star collapsed into a black hole! Escape its pull!", 4.0)

    def _nearest_planet(self) -> tuple[Planet | None, float]:
        best: Planet | None = None
        best_d = 1e9
        for pl in self.system.planets:
            if pl.consumed:
                continue
            px, py = pl.pos()
            d = dist(self.ship.x, self.ship.y, px, py)
            if d < best_d:
                best_d = d
                best = pl
        return best, best_d

    def _try_interact(self) -> None:
        pl, d = self._nearest_planet()
        if pl is None or d > pl.radius + 55:
            self._toast("No planet in range — fly closer.")
            return
        if not pl.discovered:
            pl.discovered = True
            self.discoveries.add(pl.name)
            self.score += 50
            self._toast(f"Discovered {pl.name}!", 2.0)
        self._enter_planet(pl)

    def _enter_planet(self, pl: Planet) -> None:
        if self.landed_planet is not None:
            return
        self.landed_planet = pl
        pl.landed = True
        self.ship.vx = 0.0
        self.ship.vy = 0.0
        px, py = pl.pos()
        self.ship.x = px + pl.radius + 18
        self.ship.y = py
        self.landing_t = 2.0
        self.score += 10
        self._generate_planet_map(pl)
        self.screen = "planet"
        self.dialog_planet = None
        if pl.has_aliens:
            self._toast(f"Entered {pl.name}. A local alien is nearby. Press E to meet them.", 3.0)
        else:
            self._toast(f"Entered {pl.name}. Planet scan generated — explore the surface.", 3.0)

    def _generate_planet_map(self, pl: Planet) -> None:
        seed = sum(ord(ch) for ch in pl.name)
        rng = random.Random(seed)
        terrain = ["forest", "desert", "ice", "plain", "ruins", "crater", "ocean", "mountain"]
        rows: list[list[str]] = []
        for _ in range(8):
            rows.append([terrain[rng.randrange(len(terrain))] for _ in range(8)])
        rows[3][3] = "landing"
        rows[5][6] = "ruins"
        rows[1][6] = "ocean"
        if pl.has_aliens and pl.alien_surface_pos is None:
            pl.alien_surface_pos = (4, 3)
        if not pl.surface_nodes:
            reserved = {(3, 3), (5, 6), (6, 1)}
            if pl.alien_surface_pos is not None:
                reserved.add(pl.alien_surface_pos)
            cells = [(x, y) for y in range(8) for x in range(8) if (x, y) not in reserved]
            rng.shuffle(cells)
            for node_type in ("ore", "crystal", "plants", "fuel", "fuel"):
                x, y = cells.pop()
                amount = rng.randint(15, 30) if node_type == "fuel" else rng.randint(1, 3)
                pl.surface_nodes[(x, y)] = (node_type, amount)
            if self.system.boss is not None:
                for node_type in ("rift_shard", "void_amber"):
                    x, y = cells.pop()
                    pl.surface_nodes[(x, y)] = (node_type, 1)
        self.planet_map = rows
        self.planet_map_planet = pl
        self.astronaut_pos = (3.0, 3.0)

    def _move_astronaut_on_map(self, k: str) -> None:
        dx = dy = 0.0
        if k in ("a", "left"):
            dx = -1
        elif k in ("d", "right"):
            dx = 1
        if k in ("w", "up"):
            dy = -1
        elif k in ("s", "down"):
            dy = 1
        x, y = self.astronaut_pos
        nx = clamp(x + dx, 0.0, 7.0)
        ny = clamp(y + dy, 0.0, 7.0)
        self.astronaut_pos = (nx, ny)
        pl = self.planet_map_planet
        node = pl.surface_nodes.pop((int(nx), int(ny)), None) if pl is not None else None
        if node is not None:
            node_type, amount = node
            if node_type == "fuel":
                gained = min(amount, self.ship.max_fuel - self.ship.fuel)
                self.ship.fuel += gained
                self._toast(f"Collected {int(gained)} fuel.", 2.0)
            else:
                self.resources[node_type] += amount
                self._toast(f"Collected {amount} {node_type}.", 2.0)

    def _upgrade_cost(self, upgrade: str) -> dict[str, int]:
        level = self.upgrade_levels[upgrade]
        if upgrade == "engine":
            return {"ore": 4 + 2 * level, "crystal": 2 + level}
        if upgrade == "hull":
            return {"ore": 5 + 2 * level, "plants": 3 + level}
        if upgrade == "weapon":
            return {"rift_shard": 1, "void_amber": 1}
        return {"crystal": 4 + 2 * level, "plants": 3 + level}

    def _purchase_upgrade(self, upgrade: str) -> None:
        level = self.upgrade_levels[upgrade]
        max_level = 1 if upgrade == "weapon" else 5
        if level >= max_level:
            self._toast("That ship upgrade is already at maximum level.")
            return
        cost = self._upgrade_cost(upgrade)
        if any(self.resources[resource] < amount for resource, amount in cost.items()):
            self._toast("Not enough materials for that upgrade.")
            return
        for resource, amount in cost.items():
            self.resources[resource] -= amount
        if upgrade == "engine":
            self.ship.thrust += 80
            self.ship.boost += 0.1
        elif upgrade == "hull":
            self.ship.max_hull += 25
            self.ship.hull = min(self.ship.max_hull, self.ship.hull + 25)
        elif upgrade == "weapon":
            self.weapon_damage = 150
        else:
            self.ship.max_fuel += 25
            self.ship.fuel = min(self.ship.max_fuel, self.ship.fuel + 25)
        self.upgrade_levels[upgrade] += 1
        self._toast(f"{upgrade.title()} upgrade installed! Level {self.upgrade_levels[upgrade]}.", 2.5)

    def _open_planet_map(self) -> None:
        if self.landed_planet is None:
            return
        self._generate_planet_map(self.landed_planet)
        self.screen = "planet"
        self._toast(f"Planet map ready for {self.landed_planet.name}.", 2.0)

    def _launch_from_planet(self) -> None:
        if self.landed_planet is None:
            return
        pl = self.landed_planet
        px, py = pl.pos()
        dx = self.ship.x - px
        dy = self.ship.y - py
        d = math.hypot(dx, dy)
        if d < 1:
            dx, dy, d = 0.0, -1.0, 1.0
        self.ship.x = px + dx / d * (pl.radius + 30)
        self.ship.y = py + dy / d * (pl.radius + 30)
        self.ship.vx = (dx / d) * 140.0
        self.ship.vy = (dy / d) * 140.0
        self.landed_planet = None
        pl.landed = False
        self.landing_t = 0.0
        self._toast(f"Launching from {pl.name}!", 2.0)

    def _alien_for_planet(self) -> Alien | None:
        if not self.dialog_planet:
            return None
        return self.aliens.get(self.dialog_planet.name)

    def _diplomacy_gift(self) -> None:
        al = self._alien_for_planet()
        if not al:
            return
        if self.ship.fuel < 8:
            self._toast("Not enough fuel to offer as tribute!")
            return
        self.ship.fuel -= 8
        al.step_relation(18)
        self._sync_faction(al)
        self.score += 15
        self._toast(f"You shared fuel. {al.species} trust +18 ({REL_NAMES[al.relation]})", 3.0)
        if al.relation == Relation.ALLY:
            self._toast(f"{al.species} are now ALLIES — they will defend you!", 4.0)
        self._update_alien_follow_status(al)

    def _diplomacy_talk(self) -> None:
        al = self._alien_for_planet()
        if not al:
            return
        al.step_relation(8)
        self._sync_faction(al)
        self.score += 5
        lines = [
            f"{al.species}: We watch the stars together.",
            f"{al.species}: Your ship honors our sky.",
            f"{al.species}: Peace is a good orbit.",
        ]
        self._toast(random.choice(lines) + f" ({REL_NAMES[al.relation]})", 3.5)
        self._update_alien_follow_status(al)

    def _diplomacy_fight(self) -> None:
        al = self._alien_for_planet()
        if not al:
            return
        al.step_relation(-35)
        self._sync_faction(al)
        self.ship.hull -= 15
        self._toast(f"You provoked {al.species}! Hull -15. They are {REL_NAMES[al.relation]}.", 3.5)
        if al.relation in (Relation.ENEMY, Relation.HOSTILE):
            al.active = True
        self._update_alien_follow_status(al)

    def _update_alien_follow_status(self, al: Alien) -> None:
        should_follow = al.trust <= -100 or al.trust >= 100
        if not should_follow:
            al.following_player = False
            return
        if al.following_player:
            return

        al.following_player = True
        al.in_space = True
        al.active = True
        if al.trust <= -100:
            pl = next((planet for planet in self.system.planets if planet.name == al.home_planet), None)
            if pl is not None:
                px, py = pl.pos()
                launch_angle = pl.angle + math.pi
                launch_distance = pl.radius + 65
                al.x = px + math.cos(launch_angle) * launch_distance
                al.y = py + math.sin(launch_angle) * launch_distance
            self._toast(f"{al.species} launched a fighter to attack you!", 4.0)
        else:
            al.x = self.ship.x - 70
            al.y = self.ship.y
            self._toast(f"{al.species} joined your crew and will repair your ship.", 4.0)
        al.vx = self.ship.vx
        al.vy = self.ship.vy

    def _sync_faction(self, al: Alien) -> None:
        if al.relation == Relation.ALLY:
            self.allies.add(al.species)
            self.enemies.discard(al.species)
        elif al.relation in (Relation.ENEMY, Relation.HOSTILE):
            self.enemies.add(al.species)
            self.allies.discard(al.species)

    def _update_orbits(self, dt: float) -> None:
        for star in self.system.companion_stars:
            star.angle += star.orbit_speed * dt
        for pl in self.system.planets:
            if pl.consumed:
                continue
            pl.angle += pl.orbit_speed * dt
            if self.system.black_hole:
                pl.orbit_r = max(0.0, pl.orbit_r - max(45.0, 9000.0 / max(pl.orbit_r, 40.0)) * dt)
                if pl.orbit_r <= self.system.star_radius + pl.radius:
                    pl.consumed = True
                    alien = self.aliens.get(pl.name)
                    if alien is not None:
                        alien.active = False
                    if self.landed_planet is pl:
                        self.landed_planet = None
                        self.screen = "gameover"
                        self._toast(f"{pl.name} was swallowed by the black hole!", 5.0)
                    continue
            px, py = pl.pos()
            for moon in pl.moons:
                moon.angle += moon.orbit_speed * dt
                if pl.has_aliens and pl.name in self.aliens:
                    al = self.aliens[pl.name]
                    if al.relation in (Relation.ENEMY, Relation.HOSTILE) and al.active and not al.in_space:
                        al.x = px + math.cos(moon.angle) * moon.orbit_r * 0.5
                        al.y = py + math.sin(moon.angle) * moon.orbit_r * 0.5

    def _update_ship(self, dt: float) -> None:
        s = self.ship
        if self.landed_planet is not None:
            pl = self.landed_planet
            if pl.consumed:
                self.ship.hull = 0
                return
            px, py = pl.pos()
            s.vx = 0.0
            s.vy = 0.0
            s.x = px + pl.radius + 18
            s.y = py
            return
        thrust = 0.0
        turn = 0.0
        if "w" in self.pressed or "up" in self.pressed:
            thrust = 1.0
        if "s" in self.pressed or "down" in self.pressed:
            thrust = -0.45
        if "a" in self.pressed or "left" in self.pressed:
            turn = -1.0
        if "d" in self.pressed or "right" in self.pressed:
            turn = 1.0
        s.angle += turn * 2.8 * dt
        mult = s.boost if "shift" in self.pressed else 1.0
        if thrust > 0 and s.fuel > 0:
            s.vx += math.cos(s.angle) * s.thrust * thrust * mult * dt
            s.vy += math.sin(s.angle) * s.thrust * thrust * mult * dt
            s.fuel = max(0, s.fuel - 12 * dt * mult)
        if "brake" in self.pressed:
            s.vx *= 0.92
            s.vy *= 0.92
        if self.system.black_hole:
            d_center = math.hypot(s.x, s.y)
            if d_center > 0:
                gravity = min(2400.0, 9000000.0 / (d_center * d_center))
                s.vx -= s.x / d_center * gravity * dt
                s.vy -= s.y / d_center * gravity * dt
        for star in self.system.companion_stars:
            star_x, star_y = star.pos()
            dx = s.x - star_x
            dy = s.y - star_y
            distance = math.hypot(dx, dy)
            if distance > 0:
                gravity = min(500.0, 500000.0 / (distance * distance))
                s.vx -= dx / distance * gravity * dt
                s.vy -= dy / distance * gravity * dt
        for pl in self.system.planets:
            if not pl.black_hole or pl.consumed:
                continue
            px, py = pl.pos()
            dx = s.x - px
            dy = s.y - py
            d_planet = math.hypot(dx, dy)
            if d_planet > 0:
                gravity = min(1200.0, 500000.0 / (d_planet * d_planet))
                s.vx -= dx / d_planet * gravity * dt
                s.vy -= dy / d_planet * gravity * dt
        s.vx *= 0.998
        s.vy *= 0.998
        s.x += s.vx * dt
        s.y += s.vy * dt

        for pl in self.system.planets:
            if not pl.black_hole or pl.consumed:
                continue
            px, py = pl.pos()
            if dist(s.x, s.y, px, py) <= pl.radius * 0.45:
                s.hull = 0
                self.screen = "gameover"
                self._toast(f"The black hole planet {pl.name} swallowed your ship!", 5.0)
                return

        if self.system.black_hole and not self.system.stellar_black_hole:
            if dist(s.x, s.y, 0, 0) <= self.system.star_radius * 0.45:
                s.hull = 0
                self.screen = "gameover"
                self._toast("The black hole swallowed your ship!", 5.0)
                return

        star_r = self.system.star_radius + 8
        d_star = dist(s.x, s.y, 0, 0)
        if (not self.system.black_hole or self.system.stellar_black_hole) and d_star < star_r + s.radius:
            ang = math.atan2(s.y, s.x)
            s.x = math.cos(ang) * (star_r + s.radius + 2)
            s.y = math.sin(ang) * (star_r + s.radius + 2)
            n = (s.vx, s.vy)
            if d_star > 0:
                nx = s.x / d_star
                ny = s.y / d_star
                dot = s.vx * nx + s.vy * ny
                if dot < 0:
                    s.vx -= 2.0 * dot * nx
                    s.vy -= 2.0 * dot * ny
            s.hull -= 25 * dt
            self._toast("STAR HEAT! Pull away!", 0.5)

        for star in self.system.companion_stars:
            star_x, star_y = star.pos()
            dx = s.x - star_x
            dy = s.y - star_y
            distance = math.hypot(dx, dy)
            minimum_distance = star.radius + s.radius + 4
            if distance >= minimum_distance:
                continue
            if distance == 0:
                nx, ny = 1.0, 0.0
            else:
                nx, ny = dx / distance, dy / distance
            s.x = star_x + nx * (minimum_distance + 1)
            s.y = star_y + ny * (minimum_distance + 1)
            dot = s.vx * nx + s.vy * ny
            if dot < 0:
                s.vx -= 2.0 * dot * nx
                s.vy -= 2.0 * dot * ny
            s.hull -= 18 * dt
            self._toast("Impact! A companion star clipped your hull.", 0.5)

        boss = self.system.boss
        if boss is not None and boss.active:
            dx = s.x - boss.x
            dy = s.y - boss.y
            distance = math.hypot(dx, dy)
            minimum_distance = boss.radius + s.radius
            if 0 < distance < minimum_distance:
                nx, ny = dx / distance, dy / distance
                s.x = boss.x + nx * (minimum_distance + 1)
                s.y = boss.y + ny * (minimum_distance + 1)
                dot = s.vx * nx + s.vy * ny
                if dot < 0:
                    s.vx -= 2.0 * dot * nx
                    s.vy -= 2.0 * dot * ny
                s.hull -= 24 * dt
                self._toast("The Rift Warden rammed your ship!", 0.8)

        for pl in self.system.planets:
            if pl.consumed:
                continue
            if pl.black_hole:
                continue
            px, py = pl.pos()
            dx = s.x - px
            dy = s.y - py
            d = math.hypot(dx, dy)
            min_d = pl.radius + s.radius + 6
            if d < min_d and d > 0:
                nx = dx / d
                ny = dy / d
                overlap = min_d - d
                s.x += nx * overlap
                s.y += ny * overlap
                dot = s.vx * nx + s.vy * ny
                if dot < 0:
                    s.vx -= 2.0 * dot * nx
                    s.vy -= 2.0 * dot * ny
                s.hull -= 12 * dt
                self._toast(f"Impact! {pl.name} clipped your hull.", 0.4)

    def _move_alien_toward(self, alien: Alien, target_x: float, target_y: float, speed: float, dt: float) -> float:
        dx = target_x - alien.x
        dy = target_y - alien.y
        distance = math.hypot(dx, dy)
        if distance > 1:
            alien.vx = dx / distance * speed
            alien.vy = dy / distance * speed
            alien.x += alien.vx * dt
            alien.y += alien.vy * dt
        else:
            alien.vx = alien.vy = 0.0
        return distance

    def _update_aliens(self, dt: float) -> None:
        for pl in self.system.planets:
            if pl.consumed or not pl.has_aliens or pl.name not in self.aliens:
                continue
            al = self.aliens[pl.name]
            if not al.active or al.following_player:
                continue
            px, py = pl.pos()
            if al.relation == Relation.ALLY:
                dx = self.ship.x - al.x
                dy = self.ship.y - al.y
                d = math.hypot(dx, dy)
                if d > 80:
                    al.vx = dx / d * 60
                    al.vy = dy / d * 60
                else:
                    al.vx = al.vy = 0
                al.x += al.vx * dt
                al.y += al.vy * dt
            elif al.relation in (Relation.ENEMY, Relation.HOSTILE):
                dx = self.ship.x - al.x
                dy = self.ship.y - al.y
                d = math.hypot(dx, dy)
                relentless_enemy = al.relation == Relation.ENEMY and al.trust <= -100
                if d > 1 and (d < 400 or relentless_enemy):
                    spd = 150 if relentless_enemy else 90 if al.relation == Relation.HOSTILE else 130
                    al.vx = dx / d * spd
                    al.vy = dy / d * spd
                    al.x += al.vx * dt
                    al.y += al.vy * dt
                    if d < 35:
                        damage = 28 if relentless_enemy else 18 if al.relation == Relation.ENEMY else 8
                        self.ship.hull -= damage * dt
                        if relentless_enemy:
                            self._toast(f"{al.species} are attacking your ship!", 0.6)
            else:
                al.x = px + math.cos(pl.angle * 2) * 40
                al.y = py + math.sin(pl.angle * 2) * 40

        local_planets = {planet.name for planet in self.system.planets}
        for alien in self.aliens.values():
            if not alien.active or not alien.following_player:
                continue
            if alien.relation == Relation.ENEMY and alien.trust <= -100:
                distance = self._move_alien_toward(alien, self.ship.x, self.ship.y, 150, dt)
                if distance < 35:
                    self.ship.hull -= 28 * dt
                    self._toast(f"{alien.species} are attacking your ship!", 0.6)
                continue
            if alien.relation != Relation.ALLY or alien.trust < 100:
                continue

            boss = self.system.boss
            boss_distance = math.hypot(boss.x - alien.x, boss.y - alien.y) if boss and boss.active else math.inf
            if boss is not None and boss.active and boss_distance < 600:
                boss_distance = self._move_alien_toward(alien, boss.x, boss.y, 145, dt)
                if boss_distance < boss.radius + 28:
                    self._damage_boss(120 * dt, alien.species)
            else:
                self._fight_local_enemy_or_follow(alien, local_planets, dt)

            ship_distance = math.hypot(alien.x - self.ship.x, alien.y - self.ship.y)
            if ship_distance <= 110 and self.ship.hull < self.ship.max_hull:
                self.ship.hull = min(self.ship.max_hull, self.ship.hull + 18 * dt)

    def _fight_local_enemy_or_follow(self, alien: Alien, local_planets: set[str], dt: float) -> None:
        targets = [
            enemy for enemy in self.aliens.values()
            if enemy is not alien and enemy.active
            and enemy.relation == Relation.ENEMY and enemy.trust <= -100
            and (enemy.following_player or enemy.home_planet in local_planets)
        ]
        target = min(targets, key=lambda enemy: math.hypot(enemy.x - alien.x, enemy.y - alien.y), default=None)
        target_distance = math.hypot(target.x - alien.x, target.y - alien.y) if target else math.inf
        if target is not None and target_distance < 500:
            target_distance = self._move_alien_toward(alien, target.x, target.y, 130, dt)
            if target_distance < 35:
                target.hp -= 45 * dt
                if target.hp <= 0:
                    target.active = False
                    target.following_player = False
                    self._toast(f"{alien.species} defeated {target.species}!", 3.0)
        else:
            self._move_alien_toward(alien, self.ship.x, self.ship.y, 110, dt)

    def _damage_boss(self, damage: float, attacker: str) -> None:
        boss = self.system.boss
        if boss is None or not boss.active:
            return
        boss.hp = max(0.0, boss.hp - damage)
        if boss.hp > 0:
            return
        boss.active = False
        self.boss_projectiles.clear()
        self.ship.hull = min(self.ship.max_hull, self.ship.hull + 35)
        self.ship.fuel = min(self.ship.max_fuel, self.ship.fuel + 25)
        self.score += 500
        self._toast(f"RIFT WARDEN DEFEATED by {attacker}! +500 points. The galaxy is safe!", 6.0)

    def _fire_weapon(self) -> None:
        if self.landed_planet is not None or self.weapon_cooldown > 0:
            return
        direction_x = math.cos(self.ship.angle)
        direction_y = math.sin(self.ship.angle)
        self.projectiles.append(PulseShot(
            x=self.ship.x + direction_x * 15,
            y=self.ship.y + direction_y * 15,
            vx=self.ship.vx + direction_x * 650,
            vy=self.ship.vy + direction_y * 650,
        ))
        self.weapon_cooldown = 0.22

    def _update_projectiles(self, dt: float) -> None:
        active_shots: list[PulseShot] = []
        local_planets = {planet.name for planet in self.system.planets if not planet.consumed}
        for shot in self.projectiles:
            old_x, old_y = shot.x, shot.y
            shot.x += shot.vx * dt
            shot.y += shot.vy * dt
            shot.ttl -= dt
            segment_x = shot.x - old_x
            segment_y = shot.y - old_y
            segment_length_sq = segment_x * segment_x + segment_y * segment_y
            hit_alien = False
            for alien in self.aliens.values():
                if (not alien.active or alien.relation not in (Relation.ENEMY, Relation.HOSTILE)
                        or (not alien.following_player and alien.home_planet not in local_planets)):
                    continue
                if segment_length_sq > 0:
                    fraction = clamp(
                        ((alien.x - old_x) * segment_x + (alien.y - old_y) * segment_y) / segment_length_sq,
                        0.0,
                        1.0,
                    )
                else:
                    fraction = 0.0
                closest_x = old_x + segment_x * fraction
                closest_y = old_y + segment_y * fraction
                if dist(alien.x, alien.y, closest_x, closest_y) > 20:
                    continue
                alien.hp -= self.weapon_damage
                hit_alien = True
                if alien.hp <= 0:
                    alien.active = False
                    alien.following_player = False
                    alien.in_space = False
                    self.enemies.discard(alien.species)
                    self.score += 25
                    self._toast(f"Enemy fighter {alien.species} destroyed! +25 points", 2.0)
                else:
                    self._toast(f"Hit {alien.species}!", 1.0)
                break
            boss = self.system.boss
            if not hit_alien and boss is not None and boss.active:
                if segment_length_sq > 0:
                    fraction = clamp(
                        ((boss.x - old_x) * segment_x + (boss.y - old_y) * segment_y) / segment_length_sq,
                        0.0,
                        1.0,
                    )
                else:
                    fraction = 0.0
                closest_x = old_x + segment_x * fraction
                closest_y = old_y + segment_y * fraction
                if dist(boss.x, boss.y, closest_x, closest_y) <= boss.radius + 10:
                    self._damage_boss(self.weapon_damage, "your pulse blaster")
                    hit_alien = True
                    if boss.active:
                        self._toast(f"Rift Warden hit! {int(boss.hp)} hull remaining.", 0.8)
            if not hit_alien and shot.ttl > 0:
                active_shots.append(shot)
        self.projectiles = active_shots

    def _update_boss(self, dt: float) -> None:
        boss = self.system.boss
        if boss is None or not boss.active:
            return
        boss.elapsed += dt
        boss.x = math.sin(boss.elapsed * 0.9) * 155
        boss.y = -255 + math.sin(boss.elapsed * 1.7) * 38
        boss.attack_timer -= dt
        if boss.attack_timer > 0:
            return

        phase_two = boss.hp <= boss.max_hp * 0.5
        boss.attack_timer = 0.72 if phase_two else 1.25
        base_angle = math.atan2(self.ship.y - boss.y, self.ship.x - boss.x)
        spread = (-0.32, -0.16, 0.0, 0.16, 0.32) if phase_two else (0.0,)
        speed = 300 if phase_two else 230
        damage = 13 if phase_two else 9
        for angle_offset in spread:
            angle = base_angle + angle_offset
            self.boss_projectiles.append(BossProjectile(
                x=boss.x,
                y=boss.y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                damage=damage,
            ))

    def _update_boss_projectiles(self, dt: float) -> None:
        active_projectiles: list[BossProjectile] = []
        for projectile in self.boss_projectiles:
            old_x, old_y = projectile.x, projectile.y
            projectile.x += projectile.vx * dt
            projectile.y += projectile.vy * dt
            projectile.ttl -= dt
            segment_x = projectile.x - old_x
            segment_y = projectile.y - old_y
            segment_length_sq = segment_x * segment_x + segment_y * segment_y
            if segment_length_sq > 0:
                fraction = clamp(
                    ((self.ship.x - old_x) * segment_x + (self.ship.y - old_y) * segment_y) / segment_length_sq,
                    0.0,
                    1.0,
                )
            else:
                fraction = 0.0
            closest_x = old_x + segment_x * fraction
            closest_y = old_y + segment_y * fraction
            if dist(self.ship.x, self.ship.y, closest_x, closest_y) <= self.ship.radius + 10:
                self.ship.hull -= projectile.damage
                self._toast("Rift bolt hit! Evade the Warden's volley!", 1.0)
            elif projectile.ttl > 0:
                active_projectiles.append(projectile)
        self.boss_projectiles = active_projectiles

    def _update(self, dt: float) -> None:
        self.star_pulse += dt
        self.weapon_cooldown = max(0.0, self.weapon_cooldown - dt)
        if self.msg_t > 0:
            self.msg_t -= dt
        if self.landing_t > 0:
            self.landing_t -= dt
        if self.screen not in ("fly", "planet"):
            return
        if self.screen == "fly":
            self._update_orbits(dt)
            self._update_ship(dt)
            if math.hypot(self.ship.x, self.ship.y) > self._system_edge_radius():
                self._travel_to_next_system()
            self._update_aliens(dt)
            self._update_projectiles(dt)
            self._update_boss(dt)
            self._update_boss_projectiles(dt)
            self.cam_x += (self.ship.x - self.cam_x) * min(1.0, dt * 4)
            self.cam_y += (self.ship.y - self.cam_y) * min(1.0, dt * 4)
            pl, d = self._nearest_planet()
            if pl and d < pl.radius + 80 and not pl.discovered:
                pl.discovered = True
                self.discoveries.add(pl.name)
                self.score += 50
                self._toast(f"Discovered planet {pl.name}!", 2.5)
            if self.ship.hull <= 0:
                self.screen = "gameover"
            if self.ship.fuel <= 0 and math.hypot(self.ship.vx, self.ship.vy) < 5:
                self.ship.fuel = 5
            return

        # planet map screen: keep the system moving in the background while the astronaut stays on the surface
        self._update_orbits(dt)
        self.star_pulse += dt


    def _world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        scale = 0.85
        sx = W / 2 + (wx - self.cam_x) * scale
        sy = H / 2 + (wy - self.cam_y) * scale
        return sx, sy

    def _draw_starfield(self) -> None:
        c = self.canvas
        random.seed(42)
        for _ in range(120):
            x = random.randint(0, W)
            y = random.randint(0, H)
            c.create_oval(x, y, x + 2, y + 2, fill="#fff", outline="")
        random.seed()

    def _draw_system(self) -> None:
        c = self.canvas
        sys = self.system
        c.create_rectangle(0, 0, W, H, fill=sys.bg_tint, outline="")
        self._draw_starfield()

        sx, sy = self._world_to_screen(0, 0)
        pulse = 1.0 + 0.08 * math.sin(self.star_pulse * 2)
        r = sys.star_radius * pulse
        if sys.black_hole:
            if sys.stellar_black_hole:
                corona_r = r * 1.55
                c.create_oval(sx - corona_r, sy - corona_r, sx + corona_r, sy + corona_r,
                              fill="#d94b18", outline="#ffe089", width=4, stipple="gray50")
                inner_corona_r = r * 1.18
                c.create_oval(sx - inner_corona_r, sy - inner_corona_r,
                              sx + inner_corona_r, sy + inner_corona_r,
                              fill="#ffb833", outline="#fff2ae", width=3, stipple="gray50")
            disk_w = r * 2.2
            disk_h = r * 0.65
            c.create_oval(sx - disk_w, sy - disk_h, sx + disk_w, sy + disk_h,
                          fill="#542474", outline="#77ddff", width=3)
            c.create_oval(sx - r * 0.58, sy - r * 0.58, sx + r * 0.58, sy + r * 0.58,
                          fill="#000", outline="#e6d7ff", width=3)
        elif sys.star_exploding:
            progress = 1.0 - sys.star_explosion_timer / 2.5
            blast_r = r + progress * 150
            for ring, color in enumerate(("#ff4422", "#ffbb33", "#fff0aa")):
                ring_r = blast_r * (0.62 + ring * 0.2)
                c.create_oval(sx - ring_r, sy - ring_r, sx + ring_r, sy + ring_r,
                              fill="", outline=color, width=7 - ring)
            star_r = r * (1.2 + 0.25 * math.sin(self.star_pulse * 20))
            c.create_oval(sx - star_r, sy - star_r, sx + star_r, sy + star_r,
                          fill="#fff4c2", outline="#ff5522", width=5)
        else:
            for i in range(5, 0, -1):
                gr = r + i * 18
                c.create_oval(sx - gr, sy - gr, sx + gr, sy + gr, fill=sys.star_glow, outline="", stipple="gray50")
            c.create_oval(sx - r, sy - r, sx + r, sy + r, fill=sys.star_color, outline="#fff", width=2)
        c.create_text(sx, sy - r - 16, text=sys.name, fill="#ffe", font=("Consolas", 11, "bold"))

        for star in sys.companion_stars:
            orbit_x, orbit_y = self._world_to_screen(0, 0)
            orbit_radius = star.orbit_r * 0.85
            c.create_oval(orbit_x - orbit_radius, orbit_y - orbit_radius,
                          orbit_x + orbit_radius, orbit_y + orbit_radius,
                          outline="#46384e", width=1, dash=(2, 4))
            star_x, star_y = star.pos()
            star_sx, star_sy = self._world_to_screen(star_x, star_y)
            star_pulse = 1.0 + 0.06 * math.sin(self.star_pulse * 2 + star.angle)
            star_radius = star.radius * star_pulse
            for glow_layer in range(3, 0, -1):
                glow_radius = star_radius + glow_layer * 12
                c.create_oval(star_sx - glow_radius, star_sy - glow_radius,
                              star_sx + glow_radius, star_sy + glow_radius,
                              fill=star.glow, outline="", stipple="gray50")
            c.create_oval(star_sx - star_radius, star_sy - star_radius,
                          star_sx + star_radius, star_sy + star_radius,
                          fill=star.color, outline="#fff", width=2)

        for pl in sys.planets:
            if pl.consumed:
                continue
            orx, ory = self._world_to_screen(0, 0)
            orad = pl.orbit_r * 0.85
            c.create_oval(orx - orad, ory - orad, orx + orad, ory + orad, outline="#234", width=1)

        for pl in sys.planets:
            if pl.consumed:
                continue
            px, py = pl.pos()
            mx, my = self._world_to_screen(px, py)
            if pl.black_hole:
                disk_w = pl.radius * 1.8
                disk_h = pl.radius * 0.52
                c.create_oval(mx - disk_w, my - disk_h, mx + disk_w, my + disk_h,
                              fill="#542474", outline="#77ddff", width=2)
                c.create_oval(mx - pl.radius * 0.52, my - pl.radius * 0.52,
                              mx + pl.radius * 0.52, my + pl.radius * 0.52,
                              fill="#000", outline="#e6d7ff", width=2)
            else:
                c.create_oval(mx - pl.radius, my - pl.radius, mx + pl.radius, my + pl.radius,
                              fill=pl.color, outline="#fff" if pl.discovered else "#456", width=1)
            if pl.discovered or dist(self.ship.x, self.ship.y, px, py) < pl.radius + 100:
                c.create_text(mx, my - pl.radius - 10, text=pl.name, fill="#cde", font=("Consolas", 9))
            if pl.has_aliens:
                col = "#f66" if pl.name in self.aliens and self.aliens[pl.name].relation in (
                    Relation.ENEMY, Relation.HOSTILE) else "#8f8"
                c.create_text(mx, my + pl.radius + 8, text="● aliens", fill=col, font=("Consolas", 8))
            for moon in pl.moons:
                moon_x = px + math.cos(moon.angle) * moon.orbit_r
                moon_y = py + math.sin(moon.angle) * moon.orbit_r
                mxs, mys = self._world_to_screen(moon_x, moon_y)
                c.create_oval(mxs - moon.radius, mys - moon.radius, mxs + moon.radius, mys + moon.radius,
                              fill=moon.color, outline="#789")

        local_planet_names = {pl.name for pl in sys.planets if not pl.consumed}
        visible_aliens = [self.aliens[name] for name in local_planet_names if name in self.aliens]
        visible_aliens.extend(
            alien for alien in self.aliens.values()
            if alien.following_player and alien.active and alien.home_planet not in local_planet_names
        )
        for al in visible_aliens:
            if not al.active:
                continue
            ax, ay = self._world_to_screen(al.x, al.y)
            rel = al.relation
            col = al.color
            if rel == Relation.ALLY:
                col = "#6f6"
            elif rel in (Relation.ENEMY, Relation.HOSTILE):
                col = "#f44"
            if al.in_space:
                fighter_color = "#f44" if al.trust <= -100 else "#6f6"
                angle = math.atan2(al.vy, al.vx) if math.hypot(al.vx, al.vy) > 1 else math.atan2(self.ship.y - al.y, self.ship.x - al.x)
                nose = (ax + math.cos(angle) * 13, ay + math.sin(angle) * 13)
                left = (ax + math.cos(angle + 2.45) * 10, ay + math.sin(angle + 2.45) * 10)
                right = (ax + math.cos(angle - 2.45) * 10, ay + math.sin(angle - 2.45) * 10)
                c.create_polygon(nose[0], nose[1], left[0], left[1], right[0], right[1], fill=fighter_color, outline="#fff", width=2)
            else:
                c.create_oval(ax - 12, ay - 12, ax + 12, ay + 12, fill=col, outline="#fff", width=1)
            c.create_text(ax, ay - 18, text=al.species[:8], fill=col, font=("Consolas", 8))

        boss = sys.boss
        if boss is not None:
            if boss.active:
                boss_x, boss_y = self._world_to_screen(boss.x, boss.y)
                pulse = 1.0 + 0.08 * math.sin(self.star_pulse * 5)
                glow_radius = boss.radius * 1.65 * pulse
                c.create_oval(boss_x - glow_radius, boss_y - glow_radius,
                              boss_x + glow_radius, boss_y + glow_radius,
                              fill="#a01439", outline="#ff405e", width=3, stipple="gray50")
                points = []
                for point_index in range(12):
                    angle = math.tau * point_index / 12 - math.pi / 2
                    point_radius = boss.radius if point_index % 2 == 0 else boss.radius * 0.62
                    points.extend((boss_x + math.cos(angle) * point_radius,
                                   boss_y + math.sin(angle) * point_radius))
                c.create_polygon(*points, fill="#32142d", outline="#ff6179", width=4)
                c.create_oval(boss_x - 19, boss_y - 19, boss_x + 19, boss_y + 19,
                              fill="#ff405e", outline="#ffe9aa", width=3)
                c.create_oval(boss_x - 7, boss_y - 7, boss_x + 7, boss_y + 7,
                              fill="#fff4d0", outline="")
                c.create_text(boss_x, boss_y + boss.radius + 18, text=boss.name,
                              fill="#ff8293", font=("Consolas", 10, "bold"))
            else:
                c.create_text(W // 2, H // 2 - 90, text="RIFT WARDEN DEFEATED",
                              fill="#ffe58a", font=("Consolas", 22, "bold"))

        for projectile in self.boss_projectiles:
            projectile_x, projectile_y = self._world_to_screen(projectile.x, projectile.y)
            tail_x = projectile_x - projectile.vx * 0.025
            tail_y = projectile_y - projectile.vy * 0.025
            c.create_line(tail_x, tail_y, projectile_x, projectile_y,
                          fill="#ff5268", width=5)
            c.create_oval(projectile_x - 5, projectile_y - 5,
                          projectile_x + 5, projectile_y + 5,
                          fill="#ffd18a", outline="#fff")

        for shot in self.projectiles:
            shot_x, shot_y = self._world_to_screen(shot.x, shot.y)
            tail_x = shot_x - shot.vx * 0.018
            tail_y = shot_y - shot.vy * 0.018
            c.create_line(tail_x, tail_y, shot_x, shot_y, fill="#7df", width=3)

        self._draw_rocket()

    def _draw_rocket(self) -> None:
        c = self.canvas
        s = self.ship
        sx, sy = self._world_to_screen(s.x, s.y)
        ang = s.angle
        nose = (sx + math.cos(ang) * 12, sy + math.sin(ang) * 12)
        left = (sx + math.cos(ang + 2.5) * 8, sy + math.sin(ang + 2.5) * 8)
        right = (sx + math.cos(ang - 2.5) * 8, sy + math.sin(ang - 2.5) * 8)
        c.create_polygon(nose[0], nose[1], left[0], left[1], right[0], right[1], fill="#dde", outline="#889", width=2)
        c.create_polygon(sx + math.cos(ang + 2.8) * 7, sy + math.sin(ang + 2.8) * 7,
                         sx + math.cos(ang - 2.8) * 7, sy + math.sin(ang - 2.8) * 7,
                         sx + math.cos(ang + math.pi) * 6, sy + math.sin(ang + math.pi) * 6,
                         fill="#f84", outline="")
        if math.hypot(s.vx, s.vy) > 30 or "w" in self.pressed or "up" in self.pressed:
            fx = sx + math.cos(ang + math.pi) * 9
            fy = sy + math.sin(ang + math.pi) * 9
            c.create_polygon(fx, fy,
                             fx + math.cos(ang + 2.6) * 7, fy + math.sin(ang + 2.6) * 7,
                             fx + math.cos(ang - 2.6) * 7, fy + math.sin(ang - 2.6) * 7,
                             fill="#ffcc00", outline="")

    def _draw_hud(self) -> None:
        c = self.canvas
        c.create_text(12, 12, text=f"System: {self.system.name}", fill="#adf", anchor="nw", font=("Consolas", 12, "bold"))
        c.create_text(12, 32, text=f"Planets found: {len(self.discoveries)}  Score: {self.score}", fill="#bbb", anchor="nw", font=("Consolas", 10))
        c.create_rectangle(12, 52, 212, 68, fill="#222", outline="#555")
        c.create_rectangle(13, 53, 13 + 198 * clamp(self.ship.fuel / self.ship.max_fuel, 0, 1), 67, fill="#48f", outline="")
        c.create_text(112, 60, text=f"FUEL {int(self.ship.fuel)}/{int(self.ship.max_fuel)}", fill="#fff", font=("Consolas", 9))
        c.create_rectangle(12, 74, 212, 90, fill="#222", outline="#555")
        c.create_rectangle(13, 75, 13 + 198 * clamp(self.ship.hull / self.ship.max_hull, 0, 1), 89, fill="#4c4" if self.ship.hull > self.ship.max_hull * 0.4 else "#c44", outline="")
        c.create_text(112, 82, text=f"HULL {int(self.ship.hull)}/{int(self.ship.max_hull)}", fill="#fff", font=("Consolas", 9))
        if self.allies:
            c.create_text(12, 108, text="Allies: " + ", ".join(sorted(self.allies)), fill="#8f8", anchor="nw", font=("Consolas", 9))
        if self.enemies:
            c.create_text(12, 124, text="Enemies: " + ", ".join(sorted(self.enemies)), fill="#f88", anchor="nw", font=("Consolas", 9))
        boss = self.system.boss
        if boss is not None:
            phase = 2 if boss.hp <= boss.max_hp * 0.5 else 1
            status = f"PHASE {phase}" if boss.active else "DEFEATED"
            c.create_text(W // 2, 12, text=f"{boss.name}  |  {status}",
                          fill="#ff8293" if boss.active else "#ffe58a",
                          font=("Consolas", 11, "bold"))
            bar_left, bar_top, bar_width = W // 2 - 210, 25, 420
            c.create_rectangle(bar_left, bar_top, bar_left + bar_width, bar_top + 13,
                               fill="#25151e", outline="#ff6179", width=2)
            if boss.active:
                c.create_rectangle(bar_left + 2, bar_top + 2,
                                   bar_left + 2 + (bar_width - 4) * clamp(boss.hp / boss.max_hp, 0, 1),
                                   bar_top + 11, fill="#ee3156", outline="")
        c.create_text(W // 2, H - 8, text="WASD fly | Q fire | E explore | fly past system edge to travel | M map | Esc quit",
                        fill="#889", font=("Consolas", 9))
        if self.msg_t > 0:
            c.create_rectangle(W // 2 - 280, H - 55, W // 2 + 280, H - 28, fill="#111", outline="#456")
            c.create_text(W // 2, H - 41, text=self.msg, fill="#ffe", font=("Consolas", 11))

    def _draw_galaxy_map(self) -> None:
        c = self.canvas
        c.create_rectangle(0, 0, W, H, fill="#000", stipple="gray50", outline="")
        bx, by, bw, bh = W // 2 - 220, 80, 440, 420
        c.create_rectangle(bx, by, bx + bw, by + bh, fill="#0a0a14", outline="#68f", width=2)
        page_count = (len(self.systems) + 9) // 10
        c.create_text(W // 2, 50, text=f"GALAXY MAP — page {self.galaxy_page + 1}/{page_count} — click a system or press 1-0", fill="#adf", font=("Consolas", 12, "bold"))
        first_system = self.galaxy_page * 10
        for page_slot, sys_idx in enumerate(range(first_system, min(first_system + 10, len(self.systems)))):
            sys = self.systems[sys_idx]
            y = by + 48 + page_slot * 32
            sel = sys_idx == self.system_idx
            c.create_rectangle(bx + 10, y - 12, bx + bw - 10, y + 28, fill="#1a1a28" if not sel else "#283848", outline="#f80" if sel else "#345")
            c.create_oval(bx + 24, y + 2, bx + 44, y + 22, fill=sys.star_color, outline="")
            c.create_text(bx + 58, y, text=f"{sys_idx + 1:02d}. {sys.name}  ·  {len(sys.planets)} planets", fill="#fff", anchor="w", font=("Consolas", 10, "bold"))
        c.create_text(bx + 110, by + 397, text="[ Previous page ]", fill="#9cf" if self.galaxy_page > 0 else "#456", font=("Consolas", 10))
        c.create_text(bx + bw - 110, by + 397, text="[ Next page ]", fill="#9cf" if self.galaxy_page < page_count - 1 else "#456", font=("Consolas", 10))

    def _draw_dialog(self) -> None:
        c = self.canvas
        pl = self.dialog_planet
        if not pl:
            return
        al = self.aliens.get(pl.name)
        if not al:
            return
        c.create_rectangle(0, 0, W, H, fill="#000", stipple="gray50", outline="")
        c.create_rectangle(80, 100, W - 80, H - 100, fill="#101820", outline="#6af", width=2)
        c.create_text(W // 2, 130, text=f"Planet Entry — {pl.name}", fill="#adf", font=("Consolas", 16, "bold"))
        c.create_text(W // 2, 165, text=f"Species: {al.species}  |  Status: {REL_NAMES[al.relation]}  |  Trust: {int(al.trust)}",
                      fill="#ccc", font=("Consolas", 12))
        c.create_oval(W // 2 - 40, 200, W // 2 + 40, 280, fill=al.color, outline="#fff", width=2)
        tips = (
            "E — Enter the planet and explore it\n"
            "G — Offer fuel (+trust, makes friends)\n"
            "T — Peaceful talk (+trust)\n"
            "F — Attack / insult (-trust, may become ENEMY)\n"
            "Esc — Back to space"
        )
        c.create_text(W // 2, 340, text=tips, fill="#9ab", font=("Consolas", 11), justify="center")
        if al.relation == Relation.ALLY:
            c.create_text(W // 2, 420, text="This world is safe to explore and the locals are friendly.", fill="#8f8", font=("Consolas", 11, "bold"))
        elif al.relation == Relation.ENEMY:
            c.create_text(W // 2, 420, text="The surface is dangerous — explore carefully or leave.", fill="#f88", font=("Consolas", 11, "bold"))
        else:
            c.create_text(W // 2, 420, text="The planet is fertile and ready for exploration.", fill="#9cf", font=("Consolas", 11, "bold"))

    def _draw_planet_map(self) -> None:
        c = self.canvas
        c.create_rectangle(0, 0, W, H, fill="#050b12", outline="")
        pl = self.planet_map_planet or self.landed_planet
        if pl is None:
            c.create_text(W // 2, H // 2, text="No planet map loaded", fill="#ddd", font=("Consolas", 14, "bold"))
            return

        c.create_text(W // 2, 60, text=f"Planet Scan: {pl.name}", fill="#dfeeff", font=("Consolas", 18, "bold"))
        box_x = W // 2 - 220
        box_y = 110
        grid = 46
        pad = 8
        for y in range(8):
            for x in range(8):
                tx = box_x + x * grid
                ty = box_y + y * grid
                terrain = self.planet_map[y][x]
                colors = {
                    "forest": "#4ea55c",
                    "desert": "#d7be78",
                    "ice": "#bfe9ff",
                    "plain": "#7fba5c",
                    "ruins": "#a79d7c",
                    "crater": "#7b6f66",
                    "ocean": "#3a8ed9",
                    "mountain": "#6d7d8d",
                    "landing": "#ffe07a",
                }
                c.create_rectangle(tx, ty, tx + grid - pad, ty + grid - pad, fill=colors.get(terrain, "#333"), outline="#234", width=1)
                node = pl.surface_nodes.get((x, y))
                if node is not None:
                    node_type, _ = node
                    marker = {"ore": "O", "crystal": "C", "plants": "P", "fuel": "F", "rift_shard": "R", "void_amber": "A"}[node_type]
                    marker_color = {"fuel": "#fff176", "rift_shard": "#d5a6ff", "void_amber": "#6fffe2"}.get(node_type, "#17202a")
                    c.create_text(tx + (grid - pad) / 2, ty + (grid - pad) / 2, text=marker, fill=marker_color, font=("Consolas", 15, "bold"))
                if pl.alien_surface_pos == (x, y):
                    alien = self.aliens.get(pl.name)
                    alien_color = alien.color if alien is not None else "#7df"
                    center_x = tx + (grid - pad) / 2
                    center_y = ty + (grid - pad) / 2
                    c.create_oval(center_x - 12, center_y - 12, center_x + 12, center_y + 12,
                                  fill=alien_color, outline="#fff", width=2)
                    c.create_text(center_x, center_y, text="A", fill="#101820", font=("Consolas", 11, "bold"))

        ax = box_x + self.astronaut_pos[0] * grid + (grid - pad) / 2
        ay = box_y + self.astronaut_pos[1] * grid + (grid - pad) / 2
        c.create_oval(ax - 9, ay - 9, ax + 9, ay + 9, fill="#f6f6ff", outline="#0aa", width=2)
        c.create_line(ax, ay, ax, ay - 14, fill="#0aa", width=2)
        c.create_text(W // 2, H - 136, text=f"ORE {self.resources['ore']}   CRYSTAL {self.resources['crystal']}   PLANTS {self.resources['plants']}   SHIP FUEL {int(self.ship.fuel)}/{int(self.ship.max_fuel)}", fill="#d9e8f5", font=("Consolas", 11, "bold"))
        c.create_text(W // 2, H - 112, text=f"RARE  RIFT SHARDS {self.resources['rift_shard']}   VOID AMBER {self.resources['void_amber']}", fill="#d5a6ff", font=("Consolas", 11, "bold"))
        c.create_text(W // 2, H - 90, text="O ore  C crystal  P plants  F fuel  R shard  A amber | WASD move | U upgrades | E interact", fill="#9ab", font=("Consolas", 9))
        c.create_text(W // 2, H - 54, text="Planet scan complete — the astronaut is on the surface.", fill="#8cf", font=("Consolas", 11, "bold"))

    def _draw_surface_contact(self) -> None:
        c = self.canvas
        pl = self.dialog_planet
        alien = self._alien_for_planet()
        if pl is None or alien is None:
            return
        c.create_rectangle(150, 150, W - 150, H - 140, fill="#101820", outline="#6af", width=2)
        c.create_text(W // 2, 190, text=f"You meet the {alien.species}", fill="#dff4ff", font=("Consolas", 18, "bold"))
        c.create_oval(W // 2 - 34, 220, W // 2 + 34, 288, fill=alien.color, outline="#fff", width=2)
        c.create_text(W // 2, 326, text=f"Standing: {REL_NAMES[alien.relation]}   Trust: {int(alien.trust)}", fill="#cce", font=("Consolas", 12))
        c.create_text(W // 2, 380, text="G offer fuel   |   T talk   |   F attack   |   E return to exploration", fill="#9cf", font=("Consolas", 11))

    def _draw_upgrades(self) -> None:
        c = self.canvas
        c.create_rectangle(0, 0, W, H, fill="#071019", outline="")
        c.create_text(W // 2, 72, text="SHIP WORKSHOP", fill="#dff4ff", font=("Consolas", 22, "bold"))
        c.create_text(W // 2, 112, text=f"Ore {self.resources['ore']}   Crystal {self.resources['crystal']}   Plants {self.resources['plants']}   Rift {self.resources['rift_shard']}   Amber {self.resources['void_amber']}", fill="#b9d5df", font=("Consolas", 11))
        upgrades = (
            ("engine", "1  ENGINE THRUSTERS", "Adds thrust and boost speed", f"Thrust {int(self.ship.thrust)}  |  Boost {self.ship.boost:.2f}"),
            ("hull", "2  REINFORCED HULL", "Raises hull capacity and repairs 25", f"Hull {int(self.ship.hull)}/{int(self.ship.max_hull)}"),
            ("fuel", "3  EXPANDED FUEL TANK", "Raises fuel capacity and adds fuel", f"Fuel {int(self.ship.fuel)}/{int(self.ship.max_fuel)}"),
            ("weapon", "4  RIFT LANCE", "Rare tech: triples pulse damage", f"Pulse damage {self.weapon_damage}"),
        )
        for index, (key, title, description, stat) in enumerate(upgrades):
            y = 170 + index * 90
            costs = "   ".join(f"{amount} {resource}" for resource, amount in self._upgrade_cost(key).items())
            level = self.upgrade_levels[key]
            max_level = 1 if key == "weapon" else 5
            status = "MAX LEVEL" if level >= max_level else f"Level {level}/{max_level}  |  Cost: {costs}"
            c.create_rectangle(210, y - 26, W - 210, y + 58, fill="#111e29", outline="#42677a", width=2)
            c.create_text(240, y - 9, text=title, fill="#eaf8ff", anchor="w", font=("Consolas", 14, "bold"))
            c.create_text(240, y + 13, text=description, fill="#9cb5c2", anchor="w", font=("Consolas", 10))
            c.create_text(240, y + 35, text=f"{status}  |  {stat}", fill="#bce3c5", anchor="w", font=("Consolas", 10))
        c.create_text(W // 2, H - 54, text="Press 1-4 to buy an upgrade  |  U to return to the planet", fill="#8cf", font=("Consolas", 11, "bold"))

    def _draw_title(self) -> None:
        c = self.canvas
        c.create_rectangle(0, 0, W, H, fill="#050510", outline="")
        self._draw_starfield()
        c.create_text(W // 2, 120, text="STARBOUND DIPLOMACY", fill="#adf", font=("Arial", 36, "bold"))
        c.create_text(W // 2, 175, text="Astronaut explorer — chart new worlds, meet aliens, choose war or peace.", fill="#9ab", font=("Arial", 14))
        c.create_text(W // 2, 220, text="116 solar systems · stars at the center · planets with moons · rocket flight", fill="#789", font=("Consolas", 12))
        c.create_text(W // 2, 320, text="Press Enter or Click to Launch", fill="#fc8", font=("Arial", 18, "bold"))
        c.create_text(W // 2, 400, text="Treat aliens with gifts and talk → ALLIES    Attack them → ENEMIES", fill="#8cf", font=("Consolas", 11))
        c.create_text(W // 2, 430, text="Allies defend you. Enemies chase and damage your hull.", fill="#f88", font=("Consolas", 11))
        if self.launch_button is None:
            self.launch_button = tk.Button(
                self.root,
                text="Launch Game",
                command=self._start_game,
                font=("Consolas", 12, "bold"),
                width=16,
                bg="#1b2a40",
                fg="#fff",
                activebackground="#2a3a59",
                relief="raised",
            )
            self.launch_button.place(x=W // 2 - 80, y=465)
        elif not self.launch_button.winfo_ismapped():
            self.launch_button.place(x=W // 2 - 80, y=465)

    def _draw_gameover(self) -> None:
        c = self.canvas
        self._draw_system()
        c.create_rectangle(0, 0, W, H, fill="#300", stipple="gray50", outline="")
        c.create_text(W // 2, H // 2 - 20, text="SHIP DESTROYED", fill="#f88", font=("Arial", 32, "bold"))
        c.create_text(W // 2, H // 2 + 20, text=f"Score {self.score}  ·  Planets {len(self.discoveries)}", fill="#ddd", font=("Consolas", 14))
        c.create_text(W // 2, H // 2 + 55, text="Press Enter or Space to restart", fill="#fc8", font=("Consolas", 12, "bold"))

    def _draw(self) -> None:
        self.canvas.delete("all")
        if self.screen == "title":
            self._draw_title()
        elif self.screen == "gameover":
            self._draw_gameover()
        elif self.screen == "dialog":
            self._draw_system()
            self._draw_hud()
            self._draw_dialog()
        elif self.screen == "planet":
            self._draw_planet_map()
        elif self.screen == "surface_contact":
            self._draw_planet_map()
            self._draw_surface_contact()
        elif self.screen == "upgrades":
            self._draw_upgrades()
        else:
            self._draw_system()
            self._draw_hud()
            if self.show_galaxy:
                self._draw_galaxy_map()

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(DT_CAP, now - self.last_t)
        self.last_t = now
        if self.screen in ("fly", "dialog", "planet"):
            self._update_star_event(dt)
        if self.screen in ("fly", "dialog", "planet"):
            if self.screen == "fly":
                self._update(dt)
            elif self.screen == "dialog":
                self._update_orbits(dt)
                self.star_pulse += dt
            else:
                self._update_orbits(dt)
                self.star_pulse += dt
        if self.ship.hull <= 0 and self.screen not in ("title", "gameover"):
            self.screen = "gameover"
            self.pressed.clear()
        self._draw()
        self.root.after(16, self._tick)

    def run(self) -> None:
        self._tick()
        self.root.mainloop()


def main() -> None:
    SpaceGame().run()


if __name__ == "__main__":
    main()
