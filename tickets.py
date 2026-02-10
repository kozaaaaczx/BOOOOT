import discord
import asyncio
import io
import re
import time
from discord.ui import View, Button

class TicketLauncher(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Wybierz kategorię ticketu...",
        custom_id="ticket_category_select",
        options=[
            discord.SelectOption(label="Chcę stworzyć klub", value="klub", description="Prośba o założenie nowej drużyny", emoji="🏆"),
            discord.SelectOption(label="Kontakt z administracją", value="kontakt", description="Ogólne zapytania do zarządu", emoji="📩"),
            discord.SelectOption(label="Współpraca", value="wspolpraca", description="Propozycje wspólnych projektów", emoji="🤝"),
            discord.SelectOption(label="Skarga na administrację", value="skarga_admin", description="Zgłoszenie nieprawidłowości w pracy ekipy", emoji="⚖️"),
            discord.SelectOption(label="Skarga na gracza", value="skarga_gracz", description="Zgłoszenie toksyczności lub oszustw", emoji="🚩"),
            discord.SelectOption(label="Mam propozycję", value="propozycja", description="Nowe pomysły na rozwój serwera", emoji="💡"),
            discord.SelectOption(label="Chcę zgłosić błąd", value="blad", description="Problemy techniczne i bugi", emoji="🐛"),
            discord.SelectOption(label="Inne", value="inne", description="Sprawy, które nie pasują do powyższych", emoji="❓")
        ]
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        user = interaction.user
        guild = interaction.guild
        category_name = select.values[0]
        
        # Check for existing ticket by topic (contains user ID)
        existing_channel = None
        for channel in guild.text_channels:
            if channel.topic and f"Ticket Owner: {user.id}" in channel.topic:
                existing_channel = channel
                break
        
        if existing_channel:
            await interaction.response.send_message(f"Masz już otwarty ticket: {existing_channel.mention}", ephemeral=True)
            return

        # Map values to human readable names for the embed
        category_labels = {opt.value: opt.label for opt in select.options}
        selected_label = category_labels.get(category_name, "Inne")

        # Sanitize username and category name for channel naming
        safe_username = re.sub(r'[^a-zA-Z0-9]', '', user.name.lower())
        safe_category = re.sub(r'[^a-zA-Z0-9]', '', category_name.lower())
        ticket_name = f"{safe_username}-{safe_category}"
        
        # Create permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Support role handling (specific ID)
        support_role_id = 1456730453439680748
        support_role = guild.get_role(support_role_id)
        if support_role:
             overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
             
        # Set category by ID
        target_category_id = 1456730454819471543
        category = guild.get_channel(target_category_id)
        
        try:
            channel = await guild.create_text_channel(
                name=ticket_name, 
                overwrites=overwrites, 
                category=category,
                topic=f"Ticket Owner: {user.id} | Kategoria: {selected_label}"
            )
        except Exception as e:
            await interaction.response.send_message(f"Błąd przy tworzeniu kanału: {e}", ephemeral=True)
            return

        await interaction.response.send_message(f"Stworzono ticket: {channel.mention}", ephemeral=True)
        
        # Welcome message content with specific role ping
        mentor_ping = f"<@&{support_role_id}>"
        
        # Send welcome message in the new ticket
        embed = discord.Embed(
            title=f"Witaj w Tickecie! ({selected_label})",
            description=f"Witaj {user.mention}, opisz swój problem/sprawę dotyczącą **{selected_label}**.\nAdministracja wkrótce Ci pomoże.",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"ID Użytkownika: {user.id}")
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
