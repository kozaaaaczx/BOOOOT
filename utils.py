import re
import random
from models import Player

def parse_squad_text(text):
    """
    Parses a block of text to extract player data by identifying 'Player Units'.
    A unit is usually: [Position] [Name] [OVR] or [OVR] [Name] [Position].
    """
    players = []
    
    # 1. CLEANING: Remove Discord junk
    text = re.sub(r'<[^>]+>|https?://\S+', '', text)
    
    # Polish to English position mapping
    pos_map = {
        'BR': 'GK', 'LO': 'LB', 'PO': 'RB', 'SO': 'CB', 'ŚO': 'CB',
        'SP': 'CM', 'ŚP': 'CM', 'LP': 'LM', 'PP': 'RM', 'N': 'ST',
        'NA': 'ST', 'DP': 'CDM', 'SPD': 'CDM', 'ŚPD': 'CDM',
        'SPO': 'CAM', 'ŚPO': 'CAM'
    }

    # Define Position and OVR patterns
    pos_pattern = r'(GK|LB|CB|RB|CM|LM|RM|ST|CDM|CAM|BR|LO|PO|SO|ŚO|SP|ŚP|LP|PP|N|NA|DP|SPD|ŚPD|SPO|ŚPO)'
    ovr_pattern = r'(\d{2})'

    # RE-SEARCH STRATEGY:
    # Instead of splitting lines, we find all OVRs. 
    # The text between OVRs (and some context before/after) constitutes a player.
    # However, a cleaner way is to find "Position Name OVR" or "OVR Name Position"
    
    # Match: [Position]? [Separator]? [Name] [OVR]
    # Name can contain spaces and Polish chars.
    unit_pattern = re.compile(
        fr'(?P<pos>{pos_pattern})?\s*[–\-•:|]?\s*(?P<name>[^0-9\n\r–\-•:|]+?)\s*\(?(?P<ovr>{ovr_pattern})\)?',
        re.IGNORECASE | re.UNICODE
    )

    matches = list(unit_pattern.finditer(text))
    
    if not matches:
        # Fallback to simple line-based for other formats
        lines = text.strip().split('\n')
        for line in lines:
            ovr_m = re.search(r'(\d{2})', line)
            if ovr_m:
                ovr = int(ovr_m.group(1))
                pos_m = re.search(pos_pattern, line, re.IGNORECASE)
                pos_str = pos_m.group(1).upper() if pos_m else "MD"
                name = line.replace(ovr_m.group(0), "").strip()
                if pos_m:
                    name = re.sub(fr'\b{re.escape(pos_m.group(1))}\b', '', name, flags=re.IGNORECASE).strip()
                name = re.sub(r'[()\[\]–\-:;|•]', "", name).strip()
                players.append(Player(name if name else "Unknown", ovr, pos_map.get(pos_str, pos_str)))
        return players

    for m in matches:
        raw_pos = m.group('pos')
        pos_str = raw_pos.upper() if raw_pos else "MD"
        pos = pos_map.get(pos_str, pos_str)
        
        ovr = int(m.group('ovr'))
        
        name = m.group('name').strip()
        name = re.sub(r'[()\[\]–\-:;|•]', "", name).strip()
        
        if not name or len(name) < 2:
            name = "Unknown Player"
            
        players.append(Player(name, ovr, pos))
        
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
