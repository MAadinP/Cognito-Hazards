import time
import random


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


class Sequence(Node):
    def __init__(self, name, children):
        super().__init__(name)
        self.children = children

    def execute(self, boss):
        for child in self.children:
            if not child.execute(boss):
                return False
        return True


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
    print(f"🔥 Boss (HP: {boss.health}) performs a HEAVY ATTACK!")
    boss.send_message("BOSS_ATTACK,heavy")
    time.sleep(2)  # Simulate attack cooldown


def normal_attack(boss):
    print(f"⚔️ Boss (HP: {boss.health}) performs a NORMAL ATTACK!")
    boss.send_message("BOSS_ATTACK,normal")


def heal(boss):
    heal_amount = 100 if boss.health > 500 else 200  # More healing if HP is very low
    boss.health = min(boss.health + heal_amount, 3000)
    print(f"💚 Boss heals by {heal_amount} HP! (New HP: {boss.health})")
    boss.send_message(f"BOSS_HEAL,{heal_amount}")


# **Boss AI Conditions**
def high_health(boss):
    return boss.health > 1500


def moderate_health(boss):
    return 1000 <= boss.health <= 1500


def low_health(boss):
    return boss.health < 1000


# **Construct Behavior Tree**
behavior_tree = Selector(
    "Root",
    [
        Sequence(
            "Heavy Attack Sequence",
            [
                Condition("Boss HP > 50%", high_health),
                Action("Heavy Attack", heavy_attack),
            ],
        ),
        Sequence(
            "Normal Attack Sequence",
            [
                Condition("Boss HP > 1000", moderate_health),
                Action("Normal Attack", normal_attack),
            ],
        ),
        Sequence(
            "Heal Sequence",
            [Condition("Boss HP < 1500", low_health), Action("Heal", heal)],
        ),
    ],
)


# **Boss AI Class**
class Boss:
    def __init__(self, health):
        self.health = health

    def update(self):
        behavior_tree.execute(self)

    def send_message(self, message):
        print(f"📡 Sending message to clients: {message}")


# **Print Behavior Tree**
behavior_tree.print_tree()


# **Run the AI**
boss = Boss(health=3000)

while True:
    boss.update()
    boss.health -= random.randint(200, 400)  # Simulating damage
    time.sleep(3)  # Simulate decision-making every 3 seconds
