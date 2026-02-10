import discord
from discord.ext import commands
import os
import asyncio
from models import Team, Match
from simulation import SimulationEngine
from utils import parse_squad_text, generate_random_squad
from config import *
import json
import tickets
import re

# Database file
TEAMS_DB = 'teams.json'

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# In-memory storage
teams = {}
sim_engine = SimulationEngine()

def save_teams():
    with open(TEAMS_DB, 'w', encoding='utf-8') as f:
        data = {name: team.to_dict() for name, team in teams.items()}
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_teams():
    global teams
    if os.path.exists(TEAMS_DB):
        try:
            with open(TEAMS_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
                teams = {name: Team.from_dict(team_data) for name, team_data in data.items()}
            print(f"Loaded {len(teams)} teams from {TEAMS_DB}")
        except Exception as e:
            print(f"Error loading teams: {e}")
            teams = {}

# Load teams on startup
load_teams()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        bot.add_view(tickets.TicketLauncher())
        bot.add_view(tickets.TicketControl())
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.tree.command(name="create_team", description="Stwórz nową drużynę ze składem")
async def create_team(interaction: discord.Interaction, role: discord.Role = None, nazwa: str = None, squad_text: str = ""):
    team_name = None
    if role:
        team_name = role.mention
    elif nazwa:
        team_name = nazwa
    else:
        await interaction.response.send_message("Musisz podać rolę lub nazwę drużyny!", ephemeral=True)
        return

    players = parse_squad_text(squad_text)
    if not players:
        await interaction.response.send_message("Nie udało się wykryć żadnych zawodników w tekście składu!", ephemeral=True)
        return

    new_team = Team(team_name, players)
    teams[team_name] = new_team
    save_teams()
    
    avg_ovr = new_team.get_avg_ovr()
    stars = get_star_rating(avg_ovr)
    
    summary = f"Drużyna {team_name} stworzona pomyślnie z {len(players)} zawodnikami.\n"
    summary += f"Średni OVR: {avg_ovr:.1f} | Klasa: {stars}"
    await interaction.response.send_message(summary)

@bot.tree.command(name="create_random_team", description="Stwórz losową drużynę do testów")
async def create_random_team(interaction: discord.Interaction, name: str):
    players = generate_random_squad()
    new_team = Team(name, players)
    teams[name] = new_team
    save_teams()
    await interaction.response.send_message(f"Losowa drużyna **{name}** stworzona (Średni OVR: {new_team.get_avg_ovr():.1f}).")

@bot.tree.command(name="delete_team", description="Usuń istniejącą drużynę")
async def delete_team(interaction: discord.Interaction, role: discord.Role = None, nazwa: str = None):
    team_key = None
    if role:
        team_key = role.mention
    elif nazwa:
        team_key = nazwa
    else:
        await interaction.response.send_message("Musisz podać rolę lub nazwę drużyny!", ephemeral=True)
        return

    if team_key in teams:
        del teams[team_key]
        save_teams()
        await interaction.response.send_message(f"Drużyna {team_key} została usunięta.")
    else:
        # Fuzzy search for deletion too
        found_key = None
        for k in teams.keys():
            if team_key.lower() in k.lower() or k.lower() in team_key.lower():
                found_key = k
                break
        
        if found_key:
            del teams[found_key]
            save_teams()
            await interaction.response.send_message(f"Drużyna {found_key} została usunięta (dopasowanie przybliżone).")
        else:
            await interaction.response.send_message(f"Nie znaleziono drużyny: {team_key}", ephemeral=True)

@bot.tree.command(name="edit_team", description="Edytuj skład istniejącej drużyny")
async def edit_team(interaction: discord.Interaction, role: discord.Role = None, nazwa: str = None, squad_text: str = ""):
    team_key = None
    if role:
        team_key = role.mention
    elif nazwa:
        team_key = nazwa
    else:
        await interaction.response.send_message("Musisz podać rolę lub nazwę drużyny!", ephemeral=True)
        return

    if team_key not in teams:
        # Fuzzy search
        found = False
        for k in teams.keys():
            if team_key.lower() in k.lower() or k.lower() in team_key.lower():
                team_key = k
                found = True
                break
        if not found:
            await interaction.response.send_message(f"Nie znaleziono drużyny: {team_key}", ephemeral=True)
            return

    players = parse_squad_text(squad_text)
    if not players:
        await interaction.response.send_message("Nie udało się wykryć żadnych zawodników! Skład nie został zmieniony.", ephemeral=True)
        return

    teams[team_key].players = players
    save_teams()
    
    avg_ovr = teams[team_key].get_avg_ovr()
    stars = get_star_rating(avg_ovr)
    
    summary = f"Skład drużyny {team_key} zaktualizowany ({len(players)} zawodników).\n"
    summary += f"Nowy średni OVR: {avg_ovr:.1f} | Klasa: {stars}"
    await interaction.response.send_message(summary)

def get_star_rating(ovr):
    if ovr < 60: return "0.5 ★"
    if ovr <= 62: return "1.0 ★"
    if ovr <= 64: return "1.5 ★"
    if ovr <= 66: return "2.0 ★"
    if ovr <= 68: return "2.5 ★"
    if ovr <= 70: return "3.0 ★"
    if ovr <= 74: return "3.5 ★"
    if ovr <= 78: return "4.0 ★"
    if ovr <= 82: return "4.5 ★"
    return "5.0 ★"

@bot.tree.command(name="list_teams", description="Pokaż listę wszystkich drużyn")
async def list_teams(interaction: discord.Interaction):
    if not teams:
        await interaction.response.send_message("Brak stworzonych drużyn.")
        return
    
    # Sort teams by OVR descending
    sorted_teams = sorted(teams.items(), key=lambda x: x[1].get_avg_ovr(), reverse=True)
    
    msg = "🏆 **Ranking drużyn (wg OVR):**\n"
    for i, (name, team) in enumerate(sorted_teams, 1):
        avg_ovr = team.get_avg_ovr()
        stars = get_star_rating(avg_ovr)
        
        # Use 'name' directly if it's a mention, so it "pings" (renders as a mention)
        msg += f"{i}. {name} | {stars} (OVR: {avg_ovr:.1f})\n"
        
    await interaction.response.send_message(msg)

@bot.tree.command(name="play_match", description="Rozpocznij mecz między dwiema drużynami")
async def play_match(interaction: discord.Interaction, home_role: discord.Role = None, home_name: str = None, away_role: discord.Role = None, away_name: str = None, mode: str = "live"):
    # Resolve teams
    def resolve_team(role, name):
        key = role.mention if role else name
        if not key: return None, None
        
        if key in teams:
            return key, teams[key]
        
        # Fuzzy search
        for k in teams.keys():
            if key.lower() in k.lower() or k.lower() in key.lower():
                return k, teams[k]
        return None, None

    home_key, home = resolve_team(home_role, home_name)
    away_key, away = resolve_team(away_role, away_name)

    if not home or not away:
        await interaction.response.send_message("Nie znaleziono jednej lub obu drużyn!", ephemeral=True)
        return

    # Create match instance
    match = Match(home, away, mode=mode.lower())
    
    # Check for empty teams
    if not home.players or not away.players:
        await interaction.response.send_message("Jedna z drużyn nie ma zawodników!", ephemeral=True)
        return

    # Defer response
    await interaction.response.defer()
    
    await interaction.followup.send(f"⚽ **MECZ ROZPOCZĘTY!** ⚽\n{home_key} vs {away_key}\nTryb: {mode}")
    
    # Simulation Loop
    channel = interaction.channel
    if not channel:
        channel = interaction.user # Fallback

    try:
        while not match.is_finished():
            sim_engine.simulate_minute(match)
            
            # Wait for "live" feeling
            if mode.lower() == 'live':
                 # Find events for this minute
                 events_this_minute = [log for log in match.logs if log.startswith(f"{match.current_minute}'")]
                 for event in events_this_minute:
                     try:
                         await channel.send(event)
                     except Exception as e:
                         print(f"Error sending message: {e}")

                 await asyncio.sleep(LIVE_MATCH_UPDATE_INTERVAL)
            
        
        # Match Ended
        summary = f"🏁 **KONIEC MECZU** 🏁\n{home.name} {match.home_team.score} - {match.away_team.score} {away.name}\n"
        
        # Player Ratings Report
        ratings_msg = "⭐ **Oceny Zawodników** ⭐\n\n"
        
        for team in [home, away]:
            ratings_msg += f"🔹 {team.name}:\n"
            # Sort players by rating descending
            sorted_players = sorted(team.players, key=lambda p: p.rating, reverse=True)
            for p in sorted_players:
                stats = []
                if p.goals > 0: stats.append(f"⚽x{p.goals}")
                if p.assists > 0: stats.append(f"🅰️x{p.assists}")
                if p.cards == 1: stats.append("🟨")
                if p.is_sent_off: stats.append("🟥")
                
                stats_str = f" ({', '.join(stats)})" if stats else ""
                ratings_msg += f"`{p.rating:.1f}` | **{p.name}** ({p.position}){stats_str}\n"
            ratings_msg += "\n"

        # Match Stats Summary
        stats_msg = "📊 **Statystyki Zespołowe**\n"
        stats_msg += f"Strzały: {match.stats['home_shots']} - {match.stats['away_shots']}\n"
        stats_msg += f"Celne: {match.stats['home_on_target']} - {match.stats['away_on_target']}\n"
        
        # Send full summary
        # Divide potentially long message if needed, but for Discord embed limits it should be fine for 11 vs 11
        await channel.send(summary + "\n" + stats_msg + "\n" + ratings_msg)
        
        # Man of the Match
        motm_player = calculate_motm(home, away)
        if motm_player:
            await channel.send(f"🌟 **ZAWODNIK MECZU (MOTM)** 🌟\n**{motm_player.name}** ({motm_player.position})\nOcena: **{motm_player.rating:.1f}**")
    except Exception as e:
        print(f"CRASH IN MATCH LOOP: {e}")
        await channel.send(f"🆘 **BŁĄD KRYTYCZNY:** Mecz został przerwany z powodu błędu silnika: `{e}`")

@bot.tree.command(name="setup_tickets", description="Ustaw panel ticketów na kanale (Admin)")
@commands.has_permissions(administrator=True)
async def setup_tickets(interaction: discord.Interaction, channel: discord.TextChannel):
    await tickets.setup_tickets(interaction, channel)

@bot.tree.command(name="sklad", description="Sprawdź aktualny skład drużyny")
async def sklad(interaction: discord.Interaction, role: discord.Role = None, nazwa: str = None):
    # Determine the team key
    team_key = None
    if role:
        team_key = role.mention
    elif nazwa:
        team_key = nazwa
    else:
        await interaction.response.send_message("Musisz podać rolę lub nazwę drużyny!", ephemeral=True)
        return

    if team_key not in teams:
        # Try finding by plain name if it was a role mention but stored as plain text or vice-versa
        found = False
        for k in teams.keys():
            if team_key.lower() in k.lower() or k.lower() in team_key.lower():
                team_key = k
                found = True
                break
        if not found:
            await interaction.response.send_message(f"Nie znaleziono drużyny: `{team_key}`", ephemeral=True)
            return

    team = teams[team_key]
    
    embed = discord.Embed(
        title=f"📋 Skład: {team.name}",
        color=discord.Color.green()
    )
    
    # Group players by line (GK, DEF, MID, ATT)
    gk = []
    df = []
    md = []
    fw = []
    
    for p in team.players:
        pos = p.position.upper()
        line_str = f"`{pos}` **{p.name}** ({p.ovr})"
        if pos == "GK": gk.append(line_str)
        elif pos in ["LB", "RB", "CB", "LO", "PO", "SO", "ŚO"]: df.append(line_str)
        elif pos in ["CM", "LM", "RM", "CDM", "CAM", "ŚP", "ŚPD", "ŚPO", "SP", "DP", "SPO", "LP", "PP"]: md.append(line_str)
        else: fw.append(line_str)

    if gk: embed.add_field(name="🧤 Bramkarze", value="\n".join(gk), inline=False)
    if df: embed.add_field(name="🛡️ Obrońcy", value="\n".join(df), inline=False)
    if md: embed.add_field(name="⚙️ Pomocnicy", value="\n".join(md), inline=False)
    if fw: embed.add_field(name="🎯 Napastnicy", value="\n".join(fw), inline=False)
    
    if not team.players:
        embed.description = "Brak zawodników w kadrze."
    
    avg_ovr = team.get_avg_ovr()
    stars = get_star_rating(avg_ovr)
    embed.set_footer(text=f"Klasa: {stars} | Styl: {team.style} | Graczy: {len(team.players)}")
    
    await interaction.response.send_message(embed=embed)

def calculate_motm(home_team, away_team):
    all_players = home_team.players + away_team.players
    if not all_players:
        return None
    
    # Sort by rating, then goals, then assists
    motm = max(all_players, key=lambda p: (p.rating, p.goals, p.assists))
    return motm

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("\n❌ BŁĄD: Brak zmiennej DISCORD_TOKEN w Railway Variables!")