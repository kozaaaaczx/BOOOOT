import re
import random
from models import Player

def parse_squad_text(text):
    """
    Parses a block of text to extract player data.
    Supports line-by-line and horizontal/inline formats.
    Example: GK - Stanek 79 Lo - Mauro Junior 79 Lśo - Copete 75
    """
    players = []
    
    # 1. CLEANING: Remove Discord junk
    text = re.sub(r'<[^>]+>|https?://\S+', '', text)
    
    # Position mapping (Extended Polish and English)
    pos_map = {
        'BR': 'GK', 'GK': 'GK',
        'LO': 'LB', 'LB': 'LB',
        'PO': 'RB', 'RB': 'RB',
        'SO': 'CB', 'ŚO': 'CB', 'CB': 'CB', 'LSO': 'CB', 'LŚO': 'CB', 'PSO': 'CB', 'PŚO': 'CB',
        'SP': 'CM', 'ŚP': 'CM', 'CM': 'CM', 'LSP': 'CM', 'LŚP': 'CM', 'PSP': 'CM', 'PŚP': 'CM',
        'LP': 'LM', 'LM': 'LM',
        'PP': 'RM', 'RM': 'RM',
        'N': 'ST', 'NA': 'ST', 'ST': 'ST',
        'DP': 'CDM', 'SPD': 'CDM', 'ŚPD': 'CDM', 'CDM': 'CDM',
        'SPO': 'CAM', 'ŚPO': 'CAM', 'CAM': 'CAM',
        'LS': 'LW', 'LW': 'LW',
        'PS': 'RW', 'RW': 'RW'
    }

    # Define Position and OVR patterns
    # Sorted by length to avoid partial matches (e.g. 'PŚP' before 'PŚ')
    positions = sorted(pos_map.keys(), key=len, reverse=True)
    pos_pattern = r'(' + '|'.join(re.escape(p) for p in positions) + r')'
    ovr_pattern = r'(\d{2})'

    # GLOBAL STRATEGY: Find all units of [POSITION] [TEXT] [OVR]
    # Name can contain spaces and Polish chars.
    # Pattern: Boundary + Position + Boundary + optional separator + Name + OVR
    unit_regex = re.compile(
        fr'\b(?P<pos>{pos_pattern})\b\s*[–\-\•:|]?\s*(?P<name>.*?)\s*(?P<ovr>{ovr_pattern})',
        re.IGNORECASE | re.UNICODE
    )

    matches = list(unit_regex.finditer(text))
    
    for m in matches:
        pos_code = m.group('pos').upper()
        pos_str = pos_map.get(pos_code, "MD")
        ovr = int(m.group('ovr'))
        
        # Clean name
        name = m.group('name').strip()
        name = re.sub(r'[()\[\]–\-:;|•]', " ", name)
        name = " ".join(name.split()).strip()

        if not name or len(name) < 2:
            name = "Unknown Player"
            
        players.append(Player(name, ovr, pos_str))
        
    return players


def generate_random_squad(size=11):
    names = ["Kowalski", "Nowak", "Smith", "Johnson", "Garcia", "Muller", "Rossi", "Kim", "Tanaka", "Silva", "Santos"]
    players = []
    for _ in range(size):
        name = random.choice(names) + f"_{random.randint(1,99)}"
        ovr = random.randint(65, 85)
        pos = random.choice(["GK", "CB", "MD", "ST"])
        players.append(Player(name, ovr, pos))
    return players
