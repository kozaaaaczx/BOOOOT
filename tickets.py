import discord
import asyncio
import io
import re
import time
from discord.ui import View, Button

class TicketLauncher(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Stwórz Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        
        # Check for existing ticket by topic (contains user ID)
        existing_channel = None
        for channel in guild.text_channels:
            if channel.topic and f"Ticket Owner: {user.id}" in channel.topic:
                existing_channel = channel
                break
        
        if existing_channel:
            await interaction.response.send_message(f"Masz już otwarty ticket: {existing_channel.mention}", ephemeral=True)
            return

        # Sanitize username and add ID for uniqueness
        safe_username = re.sub(r'[^a-zA-Z0-9]', '', user.name.lower())
        ticket_name = f"ticket-{safe_username}"
        
        # Create permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # support role handling
        support_role = discord.utils.get(guild.roles, name="Support")
        if support_role:
             overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
             
        # Try to find a category named "Tickets"
        category = discord.utils.get(guild.categories, name="Tickets")
        
        try:
            channel = await guild.create_text_channel(
                name=ticket_name, 
                overwrites=overwrites, 
                category=category,
                topic=f"Ticket Owner: {user.id}" # Store owner ID for robust tracking
            )
        except Exception as e:
            await interaction.response.send_message(f"Błąd przy tworzeniu kanału: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Stworzono ticket: {channel.mention}", ephemeral=True)
        
        # Welcome message content
        mentor_ping = f"{support_role.mention} " if support_role else ""
        
        # Send welcome message in the new ticket
        embed = discord.Embed(
            title="Witaj w Tickecie!",
            description="Opisz swój problem, a administracja wkrótce Ci pomoże.",
            color=discord.Color.blue()
        )
        await channel.send(f"{user.mention} {mentor_ping}", embed=embed, view=TicketControl())

class TicketControl(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij (Lock)", style=discord.ButtonStyle.secondary, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Use manage_channels instead of administrator for more granular control
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Tylko moderatorzy (Manage Channels) mogą zamykać tickety.", ephemeral=True)
            return

        channel = interaction.channel
        
        # Extract owner ID from topic
        owner_id = None
        if channel.topic and "Ticket Owner: " in channel.topic:
            try:
                owner_id = int(channel.topic.split("Ticket Owner: ")[1])
            except (ValueError, IndexError):
                pass

        # Disable the button to prevent double clicking
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Lock only the owner if found, otherwise fallback to locking all non-bot/non-default targets
        if owner_id:
            owner = interaction.guild.get_member(owner_id)
            if owner:
                await channel.set_permissions(owner, send_messages=False, read_messages=True)
                await channel.send(f"🔒 Ticket został zamknięty dla {owner.mention}.")
            else:
                 await channel.send("⚠️ Nie znaleziono właściciela ticketu na serwerze, ale kanał został zablokowany.")
        else:
            # Fallback for older channels without topic or error in topic
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Member) and target != interaction.guild.me:
                    await channel.set_permissions(target, send_messages=False, read_messages=True)
            await channel.send("🔒 Ticket został zamknięty (tryb fallback).")

    @discord.ui.button(label="Usuń", style=discord.ButtonStyle.danger, custom_id="delete_ticket_btn")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("Tylko moderatorzy mogą usuwać tickety.", ephemeral=True)
            return

        delete_timestamp = int(time.time() + 5)
        await interaction.response.send_message(f"🧨 Ticket zostanie usunięty <t:{delete_timestamp}:R>...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="Transkrypt", style=discord.ButtonStyle.primary, custom_id="transcript_ticket_btn")
    async def transcript_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        messages = [message async for message in interaction.channel.history(limit=500, oldest_first=True)]
        
        output = io.StringIO()
        output.write(f"Transkrypt ticketu: {interaction.channel.name}\n")
        output.write(f"Wygenerowano: {interaction.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for msg in messages:
            timestamp = msg.created_at.strftime("[%Y-%m-%d %H:%M:%S]")
            author = f"{msg.author.name}#{msg.author.discriminator}"
            content = msg.content if msg.content.strip() else "[Brak treści]"
            
            output.write(f"{timestamp} {author}: {content}\n")
            if msg.attachments:
                output.write(f"  [Załączniki: {', '.join([a.url for a in msg.attachments])}]\n")
        
        output.seek(0)
        file = discord.File(output, filename=f"transcript-{interaction.channel.id}.txt")
        
        await interaction.followup.send(file=file)

async def setup_tickets(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(
        title="Centrum Pomocy",
        description="Kliknij przycisk poniżej, aby otworzyć ticket kontaktowy.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed, view=TicketLauncher())
    await interaction.response.send_message(f"Panel ticketów wysłany na {channel.mention}", ephemeral=True)
