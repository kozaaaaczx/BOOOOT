import random
from config import *

class Player:
    def __init__(self, name, ovr, position="MD"):
        self.name = name
        self.ovr = int(ovr)
        self.position = position
        
        # Dynamic stats
        self.condition = 100.0  # Fatigue (0-100)
        self.rating = STARTING_RATING
        self.confidence = 0  # -3 to +3
        self.goals = 0
        self.assists = 0
        self.cards = 0
        
    def to_dict(self):
        return {
            'name': self.name,
            'ovr': self.ovr,
            'position': self.position
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(data['name'], data['ovr'], data['position'])

    def update_rating(self, amount):
        self.rating = max(1.0, min(10.0, self.rating + amount))
        
    def update_confidence(self, amount):
        # GK doesn't use confidence logic normally, but we can track it mostly for outfield
        if self.position == "GK":
            return
        self.confidence = max(-3, min(3, self.confidence + amount))

    def get_effective_ovr(self):
        # Formula: Base OVR + Confidence Impact - Fatigue Impact
        fatigue_penalty = (100 - self.condition) * 0.1
        confidence_bonus = self.confidence * 1.5
        return self.ovr + confidence_bonus - fatigue_penalty

class Team:
    def __init__(self, name, players, style=STYLE_BALANCED):
        self.name = name
        self.players = players
        self.style = style
        self.momentum = STARTING_MOMENTUM
        self.score = 0
        
    def to_dict(self):
        return {
            'name': self.name,
            'style': self.style,
            'players': [p.to_dict() for p in self.players]
        }
    
    @classmethod
    def from_dict(cls, data):
        players = [Player.from_dict(p) for p in data['players']]
        return cls(data['name'], players, data.get('style', STYLE_BALANCED))

    def get_avg_ovr(self):
        if not self.players:
            return 0
        return sum(p.ovr for p in self.players) / len(self.players)
    
    def update_momentum(self, amount):
        # Cap change per update to avoid swinging too wildly
        change = max(-MAX_MOMENTUM_CHANGE, min(MAX_MOMENTUM_CHANGE, amount))
        self.momentum = max(0, min(100, self.momentum + change))

class Match:
    def __init__(self, home_team, away_team, mode='live'):
        self.home_team = home_team
        self.away_team = away_team
        self.mode = mode
        
        self.current_minute = 0
        self.stats = {
            'home_possession': 50,
            'away_possession': 50,
            'home_shots': 0,
            'away_shots': 0,
            'home_on_target': 0,
            'away_on_target': 0,
        }
        
        self.critical_state = None  # e.g., "last_10_min"
        self.chaos_level = 0.0
        self.history = []  # List of critical events for narrative
        self.logs = [] # Full detailed log for debug or fine print
        
        # Possession tracking
        self.possession_team = None
        self.possession_streak = 0
        self.last_commentary = ""
        
    def add_event(self, minute, text, event_type=EVENT_NOTHING, important=False):
        log_entry = f"{minute}' {text}"
        self.logs.append(log_entry)
        
        if important:
            self.history.append({
                'minute': minute,
                'text': text,
                'type': event_type,
                'score': f"{self.home_team.score}-{self.away_team.score}"
            })

    def is_finished(self):
        return self.current_minute >= MATCH_LENGTH_MINUTES 
