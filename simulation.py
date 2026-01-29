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
        
        # 2. DECISION LAYER (Dynamic Match Pacing)
        # Base neutral chance decreases slightly over time to increase action in late game
        base_neutral = 0.90
        if minute > 30: base_neutral -= 0.05
        if minute > 70: base_neutral -= 0.05
        
        neutral_chance = base_neutral
        
        # INCREASE ACTION if score is tied or very close (1 goal diff)
        score_diff_abs = abs(match.home_team.score - match.away_team.score)
        if score_diff_abs <= 1:
            neutral_chance -= 0.05
            
        # Reduce 'nothing happens' if momentum is high or streak is active
        if match.possession_streak > 0:
            neutral_chance -= 0.1
        if abs(match.home_team.momentum - match.away_team.momentum) > 20:
            neutral_chance -= 0.1
            
        if match.chaos_level > 0.5:
            neutral_chance -= 0.1
            
        # Final safety bounds
        neutral_chance = max(0.55, min(0.95, neutral_chance))
            
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
             # Momentum influence refined
             mom_diff = (match.home_team.momentum - match.away_team.momentum)
             home_ovr_diff = (match.home_team.get_avg_ovr() - match.away_team.get_avg_ovr())
             
             home_adv = home_ovr_diff + (mom_diff / 10)
             
             # CATCH-UP MECHANIC: If winning by 2+, reduce possession chance
             score_diff = match.home_team.score - match.away_team.score
             if score_diff >= 2:
                 home_adv -= (5 * score_diff) # Scalable penalty
             elif score_diff <= -2:
                 home_adv += (5 * abs(score_diff)) # Scalable bonus
                 
             home_prob = 0.5 + (home_adv / 100)
             home_prob = max(0.2, min(0.8, home_prob)) # Caps
             
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
        # Function to check if player is GK
        def is_gk(p):
            return p.position.strip().upper() in ["GK", "BR", "BRAMKARZ", "GOALKEEPER"]
            
        outfield_players = [p for p in att_team.players if not is_gk(p)]
        
        # Double check: if still finding a GK (e.g. position naming mismatch), skip them
        if not outfield_players:
            # Fallback: just pick anyone but try to avoid the one with 'GK' in stats if possible
            outfield_players = att_team.players
            
        attacker = random.choice(outfield_players)
        
        # Paranoia check: If we somehow picked a GK, pick again from others
        if is_gk(attacker) and len(att_team.players) > 1:
             others = [p for p in att_team.players if p != attacker]
             if others:
                 attacker = random.choice(others)

        # Apply Weighted Selection
        # ST/CF/LF/RF -> Weight 10
        # CAM/LM/RM/LW/RW -> Weight 7
        # CM/CDM -> Weight 4
        # CB/LB/RB/WB -> Weight 1
        weights = []
        for p in outfield_players:
            pos = p.position.strip().upper()
            if pos in ["ST", "CF", "LF", "RF", "NAPASTNIK"]:
                w = 10
            elif pos in ["CAM", "LM", "RM", "LW", "RW", "POMOCNIK"]:
                w = 7
            elif pos in ["CM", "CDM", "ŚPD", "ŚP"]:
                w = 4
            else:
                w = 1 # Defenders
            
            # SCORER COOLDOWN / DIMINISHING RETURNS
            # If player has scored, reduce their weight to prevent one person dominating (e.g. Lewandowski 7 goals)
            # Formula: New Weight = Weight / (1 + Goals * 2)
            if p.goals > 0:
                w = w / (1 + p.goals * 3) # Even harsher cooldown
                
            weights.append(w)
            
        attacker = random.choices(outfield_players, weights=weights, k=1)[0]

        # Find goalkeeper
        gk = next((p for p in def_team.players if p.position.upper() in ["GK", "BR"]), None)
        if not gk:
            gk = def_team.players[0]

        # Action Roll
        # Attack roll vs Defense roll
        # Normalized variance
        att_score = attacker.get_effective_ovr() + random.randint(-12, 12)
        def_score = gk.get_effective_ovr() + random.randint(-8, 8) + 5
        
        # Momentum impact - Quadratic-ish factor
        mom_diff = (att_team.momentum - def_team.momentum)
        att_score += (mom_diff / 5) # Increased weight of momentum for variety
        
        # CATCH-UP LOGIC vs SNOWBALL PREVENTION
        # If attacking team is winning by 2+, they relax slightly (lower score)
        # If attacking team is losing by 2+, they push harder (higher score)
        score_diff = att_team.score - def_team.score
        if score_diff >= 2:
            att_score -= 5 # Complacency
            # MERCY RULE: If winning by 4+, massive penalty (prevent 10-1 carnage)
            if score_diff >= 4:
                att_score -= 15
        elif score_diff <= -2:
            att_score += 5 # Desperation push
        
        # Chaos factor - Reduced randomness to prevent wild swings
        if random.random() < match.chaos_level:
            att_score += random.randint(-15, 15) # Was -25, 25
        
        context = {'team': att_team, 'player': attacker, 'opponent': def_team}

        # Events
        # AGGRESSIVE SUPPRESSION: Goal threshold is dynamic
        # Base is +15. For every goal the team already has, it increases by +5
        # If team has 2 goals, threshold is 15 + 10 = 25.
        target_threshold = 15 + (att_team.score * 5)
        
        if att_score > def_score + target_threshold:
            # GOAL
            return EVENT_GOAL, context
        elif att_score > def_score + 5:
            # SAVE (GK heroics)
            context['player'] = gk 
            return EVENT_SAVE, context
        elif att_score > def_score - 1:
             # SHOT 
             return EVENT_SHOT, context
        
        # RANDOM FOULS (Chaos dependent)
        foul_roll = random.random()
        if foul_roll < (0.05 + (match.chaos_level * 0.1)):
            if foul_roll < 0.005: # High punishment
                return EVENT_RED_CARD, context
            elif foul_roll < 0.02:
                return EVENT_YELLOW_CARD, context
            return EVENT_FOUL, context
            
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
            # Reduced from 0.5 to 0.3 to prevent GKs from dominating MOTM in 0-0/1-0 games
            player.update_rating(0.3)
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
            player.update_rating(0.3) # Increased from 0.2
            
        elif event_type == EVENT_YELLOW_CARD:
            player.update_rating(-0.2)
            player.update_confidence(-1)
            match.chaos_level += 0.02

        elif event_type == EVENT_FOUL:
            player.update_rating(-0.1)
            match.chaos_level += 0.01

        elif event_type == EVENT_ATTACK:
            # Slight momentum build
            att_team.update_momentum(3)
            player.update_rating(0.2) # Increased from 0.1
