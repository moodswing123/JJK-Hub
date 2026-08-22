import os
import sys

os.environ.setdefault('POSTGRES_URL', 'postgresql://startup-test.invalid/db')
os.environ.setdefault('OWNER_ID', '0')

import database
import game_engine
import image_generator
import expansion_system

class FakeDatabase:
    def __init__(self):
        pass

class FakeGameEngine:
    def __init__(self, db):
        self.db = db

class FakeImageGenerator:
    pass

class FakeExpansionSystem:
    def __init__(self, db=None):
        self.db = db

database.Database = FakeDatabase
game_engine.GameEngine = FakeGameEngine
image_generator.ImageGenerator = FakeImageGenerator
expansion_system.ExpansionSystem = FakeExpansionSystem

sys.modules.pop('bot', None)
import bot  # noqa: F401,E402
print('Railway bot startup import passed with manifest dependencies')
