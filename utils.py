import re
import random
from models import Player

def parse_squad_text(text):
    """
    Parses a block of text to extract player data.
    Supports formats like:
    LB – Lorenzo Insigne (76)
    GK: Jan Kowalski 80
    ST Robert Lewandowski 90
    """
    players = []
    
    # 1. CLEANING: Remove Discord junk
    text = re.sub(r'<[^>]+>|https?://\S+', '', text)
    
    # Position mapping (Polish and English)
    pos_map = {
        'BR': 'GK', 'GK': 'GK',
        'LO': 'LB', 'LB': 'LB',
        'PO': 'RB', 'RB': 'RB',
        'SO': 'CB', 'ŚO': 'CB', 'CB': 'CB',
        'SP': 'CM', 'ŚP': 'CM', 'CM': 'CM',
        'LP': 'LM', 'LM': 'LM',
        'PP': 'RM', 'RM': 'RM',
        'N': 'ST', 'NA': 'ST', 'ST': 'ST',
        'DP': 'CDM', 'SPD': 'CDM', 'ŚPD': 'CDM', 'CDM': 'CDM',
        'SPO': 'CAM', 'ŚPO': 'CAM', 'CAM': 'CAM'
    }

    # Define Position and OVR patterns with strict boundaries
    pos_pattern = r'(GK|LB|CB|RB|CM|LM|RM|ST|CDM|CAM|BR|LO|PO|SO|ŚO|SP|ŚP|LP|PP|N|NA|DP|SPD|ŚPD|SPO|ŚPO)'
    ovr_pattern = r'(\d{2})'

    # Process line by line for better control
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue

        # Find OVR first
        ovr_match = re.search(ovr_pattern, line)
        if not ovr_match: continue
        ovr = int(ovr_match.group(1))

        # Find position at the beginning or surrounded by boundaries
        # Look for position at start of line or following a separator
        pos_match = re.search(fr'^{pos_pattern}|(?<=[^a-zA-Z]){pos_pattern}(?=[^a-zA-Z])', line, re.IGNORECASE)
        
        pos_str = "MD"
        if pos_match:
            pos_code = pos_match.group(0).upper()
            pos_str = pos_map.get(pos_code, "MD")
            
        # Extract name: remove OVR and Position parts
        name = line
        if ovr_match:
            name = name.replace(ovr_match.group(0), "")
        if pos_match:
            # We must be careful not to replace part of a word
            # Only replace the specific position match we found
            pos_span = pos_match.span()
            name = name[:pos_span[0]] + name[pos_span[1]:]

        # Final cleanup of name
        name = re.sub(r'[()\[\]–\-:;|•]', " ", name)
        name = " ".join(name.split()).strip() # Remove double spaces

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
