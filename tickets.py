import discord
import asyncio
import io
import re
from discord.ui import View, Button

class TicketLauncher(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Stwórz Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        guild = interaction.guild
        
        # Sanitize username and add ID for uniqueness
        safe_username = re.sub(r'[^a-zA-Z0-9]', '', user.name.lower())
        ticket_name = f"ticket-{safe_username}-{user.id}"
        
        existing_channel = discord.utils.get(guild.text_channels, name=ticket_name)
        
        if existing_channel:
            await interaction.response.send_message(f"Masz już otwarty ticket: {existing_channel.mention}", ephemeral=True)
            return

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
             
        # Try to find a category named "Tickets" (optional improvement)
        category = discord.utils.get(guild.categories, name="Tickets")
        
        try:
            channel = await guild.create_text_channel(name=ticket_name, overwrites=overwrites, category=category)
        except Exception as e:
            await interaction.response.send_message(f"Błąd przy tworzeniu kanału: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Stworzono ticket: {channel.mention}", ephemeral=True)
        
        # Send welcome message in the new ticket
        embed = discord.Embed(
            title="Witaj w Tickecie!",
            description="Opisz swój problem, a administracja wkrótce Ci pomoże.",
            color=discord.Color.blue()
        )
        await channel.send(f"{user.mention}", embed=embed, view=TicketControl())

class TicketControl(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Zamknij (Lock)", style=discord.ButtonStyle.secondary, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Tylko administratorzy mogą zamykać tickety.", ephemeral=True)
            return

        channel = interaction.channel
        
        # Disable the button to prevent double clicking
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Lock the ticket
        for target, overwrite in channel.overwrites.items():
             # Lock for regular members (excluding bots/support if we wanted, but generally lock for the user)
            if isinstance(target, discord.Member) and target != interaction.guild.me:
                await channel.set_permissions(target, send_messages=False, read_messages=True)

        embed = discord.Embed(description="🔒 **Ticket został zamknięty przez moderatora.**", color=discord.Color.red())
        await channel.send(embed=embed)

    @discord.ui.button(label="Usuń", style=discord.ButtonStyle.danger, custom_id="delete_ticket_btn")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Tylko administratorzy mogą usuwać tickety.", ephemeral=True)
            return

        await interaction.response.send_message("🧨 Ticket zostanie usunięty za 5 sekund...")
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
            author = f"{msg.author.name}#{msg.author.discriminator}" # Discriminator is often 0 now, but safe to include
            output.write(f"{timestamp} {author}: {msg.content}\n")
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
