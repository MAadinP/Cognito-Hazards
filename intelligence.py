import random
import time


class Node:
    def __init__(self, name):
        self.name = name

    def execute(self, boss):
        pass

    def print_tree(self, level=0):
        print("  " * level + self.name)


class Selector(Node):
    def __init__(self, name, children):
        super().__init__(name)
        self.children = children

    def execute(self, boss):
        for child in self.children:
            if child.execute(boss):
                return True
        return False

    def print_tree(self, level=0):
        print("  " * level + f"[Selector] {self.name}")
        for child in self.children:
            child.print_tree(level + 1)


class Sequence(Node):
    def __init__(self, name, children):
        super().__init__(name)
        self.children = children

    def execute(self, boss):
        for child in self.children:
            if not child.execute(boss):
                return False
        return True

    def print_tree(self, level=0):
        print("  " * level + f"[Sequence] {self.name}")
        for child in self.children:
            child.print_tree(level + 1)


class Condition(Node):
    def __init__(self, name, condition_func):
        super().__init__(name)
        self.condition_func = condition_func

    def execute(self, boss):
        return self.condition_func(boss)


class Action(Node):
    def __init__(self, name, action_func):
        super().__init__(name)
        self.action_func = action_func

    def execute(self, boss):
        self.action_func(boss)
        return True


# **Boss AI Actions**
def heavy_attack(boss):
    print("🔥 Boss performs a HEAVY ATTACK!")
    boss.send_message("BOSS_ATTACK,heavy")
    time.sleep(2)  # Pause after attack


def normal_attack(boss):
    print("⚔️ Boss performs a NORMAL ATTACK!")
    boss.send_message("BOSS_ATTACK,normal")


def heal(boss):
    print("💚 Boss is HEALING!")
    boss.send_message("BOSS_HEAL")
    boss.health = min(boss.health + 200, 3000)  # Heal up to max HP


# **Boss AI Conditions**
def enemy_near(boss):
    return boss.enemy_distance < 10


def high_health(boss):
    return boss.health > 1500


def low_health(boss):
    return boss.health < 1000


# **Construct Behavior Tree**
behavior_tree = Selector(
    "Root",
    [
        Sequence(
            "Heavy Attack Sequence",
            [
                Condition("Enemy Near?", enemy_near),
                Condition("Boss HP > 50%", high_health),
                Action("Heavy Attack", heavy_attack),
            ],
        ),
        Sequence(
            "Normal Attack Sequence",
            [
                Condition("Enemy Near?", enemy_near),
                Action("Normal Attack", normal_attack),
            ],
        ),
        Sequence(
            "Heal Sequence",
            [Condition("Boss HP < 30%", low_health), Action("Heal", heal)],
        ),
    ],
)


# **Boss AI Class**
class Boss:
    def __init__(self):
        self.health = 3000
        self.enemy_distance = 5  # Simulated enemy position

    def update(self):
        behavior_tree.execute(self)

    def send_message(self, message):
        print(f"📡 Sending message to clients: {message}")


# **Run the AI**
boss = Boss()
behavior_tree.print_tree()

while True:
    boss.update()
    time.sleep(3)  # Simulate AI decision-making every 3 seconds
