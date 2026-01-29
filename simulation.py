import random
from config import *
from models import Match, Player, Team
from commentary import CommentaryEngine

class SimulationEngine:
    def __init__(self):
        self.commentator = CommentaryEngine()

    def simulate_minute(self, match: Match):
        match.current_minute += 1
        minute = match.current_minute
        
        # 1. UPDATE STATE
        self._update_fatigue(match)
        self._update_chaos(match)
        
        # 2. DECISION LAYER (Balance Rule)
        neutral_chance = 0.85
        # Reduce 'nothing happens' significantly if momentum is high or streak is active
        if match.possession_streak > 0:
            neutral_chance -= 0.3 # Was 0.2
        if abs(match.home_team.momentum - match.away_team.momentum) > 15:
            neutral_chance -= 0.2
            
        if match.chaos_level > 0.4:
            neutral_chance -= 0.15
            
        # Ensure it doesn't go too low
        neutral_chance = max(0.3, neutral_chance) # Was 0.4
            
        if random.random() < neutral_chance:
            # If we are NOT in a pressure phase, we do a neutral event
            event_text = self.commentator.get_commentary(match, EVENT_NOTHING)
            
            if hasattr(match, 'last_commentary') and match.last_commentary == event_text:
                event_text = self.commentator.get_commentary(match, EVENT_NOTHING)

            match.last_commentary = event_text
            
            if match.mode == 'live': 
                match.add_event(minute, event_text)
            return

        # 3. DETERMINE POSSESSION (Phase Logic)
        # If a team has a streak, they likely keep the ball
        # Reduced stickiness from 0.7 to 0.6 to allow more turnovers
        if match.possession_team and random.random() < 0.6:
             attacking_team = match.possession_team
             match.possession_streak += 1
        else:
             # Regular OVR/Momentum based toss
             # Reduced momentum impact on possession from /4 to /8
             home_adv = (match.home_team.get_avg_ovr() - match.away_team.get_avg_ovr()) + (match.home_team.momentum - match.away_team.momentum) / 8
             
             # CATCH-UP MECHANIC: If home is winning by 2+, reduce their possession chance
             score_diff = match.home_team.score - match.away_team.score
             if score_diff >= 2:
                 home_adv -= 15
             elif score_diff <= -2:
                 home_adv += 15
                 
             home_prob = 0.5 + (home_adv / 100)
             attacking_team = match.home_team if random.random() < home_prob else match.away_team
             match.possession_team = attacking_team
             match.possession_streak = 0

        defending_team = match.away_team if attacking_team == match.home_team else match.home_team
        
        # 4. OUTCOME RESOLUTION
        event_type, context = self._resolve_action(match, attacking_team, defending_team)
        
        # 5. APPLY OUTCOME & LOGGING
        self._apply_outcome(match, event_type, context)
        
        text = self.commentator.get_commentary(match, event_type, context)
        if text:
             # Important events check for history
            important = event_type in [EVENT_GOAL, EVENT_RED_CARD, EVENT_SAVE]
            match.add_event(minute, text, event_type, important)

    def _update_fatigue(self, match):
        for team in [match.home_team, match.away_team]:
            for player in team.players:
                # Fatigue grows linearly with some random variance
                drop = random.uniform(0.05, 0.15)
                player.condition = max(0, player.condition - drop)

    def _update_chaos(self, match):
        # Increase chaos in last 10 mins or if score is close
        if match.current_minute > 80:
            match.chaos_level = min(MAX_CHAOS_LEVEL, match.chaos_level + 0.05)
        
        score_diff = abs(match.home_team.score - match.away_team.score)
        if score_diff == 0:
             match.chaos_level = min(MAX_CHAOS_LEVEL, match.chaos_level + 0.01)

    def _resolve_action(self, match, att_team, def_team):
        # Pick attacker (STRICTLY Exclude GKs)
        # We check common names/tags for GKs
        outfield_players = [p for p in att_team.players if p.position.upper() not in ["GK", "BR", "BRAMKARZ"]]
        
        # Double check: if still finding a GK (e.g. position naming mismatch), skip them
        if not outfield_players:
            outfield_players = att_team.players
            
        attacker = random.choice(outfield_players)
        # If by any chance we picked Pavlenka or any GK, try to pick someone else
        if attacker.position.upper() in ["GK", "BR"] and len(att_team.players) > 1:
             attacker = random.choice([p for p in att_team.players if p != attacker])

        # Find goalkeeper
        gk = next((p for p in def_team.players if p.position.upper() in ["GK", "BR"]), None)
        if not gk:
            gk = def_team.players[0]

        # Action Roll
        # Attack roll vs Defense roll
        # Increased variance significantly to allow for shocks
        att_score = attacker.get_effective_ovr() + random.randint(-15, 20)
        def_score = gk.get_effective_ovr() + random.randint(-10, 15) + 5 # Lower GK bonus
        
        # Momentum impact - Decreased impact to prevent snowballing
        att_score += (att_team.momentum - 50) / 6
        
        # CATCH-UP LOGIC vs SNOWBALL PREVENTION
        # If attacking team is winning by 2+, they relax slightly (lower score)
        # If attacking team is losing by 2+, they push harder (higher score)
        score_diff = att_team.score - def_team.score
        if score_diff >= 2:
            att_score -= 5 # Complacency
        elif score_diff <= -2:
            att_score += 5 # Desperation push
        
        # Chaos factor - Increased
        if random.random() < match.chaos_level:
            att_score += random.randint(-25, 25)
        
        context = {'team': att_team, 'player': attacker, 'opponent': def_team}

        # Events
        # AGGRESSIVE TUNING: Goal threshold lowered to +8 (was +15)
        if att_score > def_score + 8:
            # GOAL
            return EVENT_GOAL, context
        elif att_score > def_score + 2:
            # SAVE (GK heroics)
            context['player'] = gk 
            return EVENT_SAVE, context
        elif att_score > def_score - 4:
             # SHOT 
             return EVENT_SHOT, context
        else:
             return EVENT_ATTACK, context

    def _apply_outcome(self, match, event_type, context):
        att_team = context.get('team')
        player = context.get('player') # This might be GK in save context
        
        if event_type == EVENT_GOAL:
            att_team.score += 1
            att_team.update_momentum(10) # Reduced from 20
            player.update_rating(1.0)
            player.update_confidence(2)
            player.goals += 1
            match.chaos_level += 0.05 # Reduced from 0.1
            
        elif event_type == EVENT_SAVE:
            # Player is GK here
            player.update_rating(0.5)
            # Defending team gets momentum boost
            def_team = match.home_team if att_team == match.away_team else match.away_team
            def_team.update_momentum(10)
            
        elif event_type == EVENT_RED_CARD:
            player.update_rating(-2.0)
            player.cards += 1
            match.chaos_level += 0.3
            # In a real engine, we'd remove the player from the list, but for simplicity we keep them but tank their stats or simple ignore
            player.ovr = 0 # Effective removal
            
        elif event_type == EVENT_SHOT:
            player.update_confidence(1)
            player.update_rating(0.2)
            
        elif event_type == EVENT_ATTACK:
            # Slight momentum build
            att_team.update_momentum(3)
            player.update_rating(0.1)
