import discord
import os
import asyncio
from dotenv import load_dotenv
import traceback # Import traceback for better error logging

# --- Configuration ---
load_dotenv() # Load variables from .env file for local testing (optional)

# Get configuration from environment variables (Essential for Railway)
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SUPPORT_ROLE_ID_STR = os.getenv("SUPPORT_ROLE_ID")
TICKET_CATEGORY_ID_STR = os.getenv("TICKET_CATEGORY_ID")

# --- Validate Configuration ---
CONFIG_ERROR = False
if not BOT_TOKEN:
    print("ERROR: DISCORD_BOT_TOKEN environment variable not set.")
    CONFIG_ERROR = True
if not SUPPORT_ROLE_ID_STR:
    print("ERROR: SUPPORT_ROLE_ID environment variable not set.")
    CONFIG_ERROR = True
if not TICKET_CATEGORY_ID_STR:
    print("ERROR: TICKET_CATEGORY_ID environment variable not set.")
    CONFIG_ERROR = True

# Attempt to convert IDs to integers
SUPPORT_ROLE_ID = None
TICKET_CATEGORY_ID = None
try:
    if SUPPORT_ROLE_ID_STR:
        SUPPORT_ROLE_ID = int(SUPPORT_ROLE_ID_STR)
    if TICKET_CATEGORY_ID_STR:
        TICKET_CATEGORY_ID = int(TICKET_CATEGORY_ID_STR)
except ValueError:
    print("ERROR: SUPPORT_ROLE_ID or TICKET_CATEGORY_ID is not a valid integer.")
    CONFIG_ERROR = True

if CONFIG_ERROR:
    # Use exit() to ensure the script stops if config is bad
    exit("Exiting due to configuration errors. Please set the required environment variables.")

# --- Bot Code ---

# Define necessary intents
intents = discord.Intents.default()
intents.guilds = True       # Need guild info to get roles/channels

client = discord.Client(intents=intents)

# --- Define the Modal (Popup Form) --- ### THIS IS THE UPDATED MODAL ###
class InfoModal(discord.ui.Modal, title='请提供必要信息以处理您的请求'):

    # --- NEW: Field for Role ID / Profile Link ---
    identifier = discord.ui.TextInput(
        label='角色ID 或 个人资料链接 (用于身份确认)',
        style=discord.TextStyle.short, # Single line is likely enough
        placeholder='请提供相关ID或链接',
        required=True,
        max_length=150, # Allow more space for links
    )

    # --- NEW: Field for Reason for Contact ---
    reason = discord.ui.TextInput(
        label='请说明来意 (Reason for contact)',
        style=discord.TextStyle.paragraph, # Allow multi-line input for detailed reasons
        placeholder='例如：申请GJ正式成员/GJZ精英部队/GJK前鋒部队/合作/或其他...',
        required=True,
        max_length=1000, # Allow ample space for explanation
    )

    # --- Kept the Kill Count field, made optional ---
    kill_count = discord.ui.TextInput(
        label='(如果适用) 你大概多少杀？',
        style=discord.TextStyle.short,
        placeholder='例如：50+ (若不适用可填 N/A)', # Updated placeholder
        required=False, # Make it optional
        max_length=50,
    )

    # --- Kept the Optional Notes field ---
    notes = discord.ui.TextInput(
        label='其他补充说明 (Optional Notes)',
        style=discord.TextStyle.paragraph,
        placeholder='任何其他需要让客服知道的信息...',
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        # This is called when the user clicks "Submit" in the modal

        user = interaction.user

        # Format the collected information into an Embed
        result_embed = discord.Embed(
            title="📄 用户提交的 Ticket 信息",
            description=f"由 {user.mention} ({user.id}) 提交",
            color=discord.Color.blue()
        )
        # --- Add the NEW fields to the result embed ---
        result_embed.add_field(name="身份标识 (ID/链接)", value=self.identifier.value, inline=False)
        result_embed.add_field(name="来意说明", value=self.reason.value, inline=False)

        # --- Add the existing fields (conditionally) ---
        if self.kill_count.value: # Only show kill count if user provided a value
             result_embed.add_field(name="大致击杀数", value=self.kill_count.value, inline=False)
        if self.notes.value: # Only show notes if provided
            result_embed.add_field(name="补充说明", value=self.notes.value, inline=False)

        result_embed.set_thumbnail(url=user.display_avatar.url) # Use user's avatar
        result_embed.set_footer(text=f"Ticket: {interaction.channel.name} | Status: Info Provided")

        # Send the formatted information into the ticket channel
        await interaction.channel.send(embed=result_embed)

        # Send ephemeral confirmation to the user
        await interaction.response.send_message("✅ 你的信息已提交！客服人员会尽快查看。", ephemeral=True, delete_after=15)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        # Handle errors during submission
        print(f"Error in InfoModal submission: {error}")
        traceback.print_exc() # Print full error traceback for debugging
        await interaction.response.send_message('提交信息时发生错误，请稍后重试或联系管理员。', ephemeral=True)

# --- Define the View with the Button --- ### THIS REMAINS THE SAME ###
class InfoButtonView(discord.ui.View):
    def __init__(self, *, timeout=180): # Default timeout 180 seconds
        super().__init__(timeout=timeout)
        self.message = None # To store the message later if needed for timeout handling

    @discord.ui.button(label="📝 提供信息 (Provide Info)", style=discord.ButtonStyle.primary, custom_id="provide_ticket_info")
    async def provide_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Send the Modal when button is clicked
        modal = InfoModal()
        await interaction.response.send_modal(modal)

    # Optional: Handle view timeout (disable button)
    async def on_timeout(self):
        print(f"InfoButtonView for message {self.message.id if self.message else 'Unknown'} timed out.")
        # Disable the button
        self.provide_info_button.disabled = True
        # Try to edit the original message to show the disabled button
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                print("Original message for timed out view not found.")
            except discord.Forbidden:
                print("Bot lacks permission to edit the message for timed out view.")
            except Exception as e:
                 print(f"Error editing message on view timeout: {e}")
        # Stop listening for interactions on this view
        self.stop()

@client.event
async def on_ready():
    """Called when the bot successfully connects."""
    print(f'Bot logged in as {client.user}')
    print(f'Monitoring Category ID: {TICKET_CATEGORY_ID}')
    print(f'Adding Support Role ID: {SUPPORT_ROLE_ID}')
    try:
        # Set bot presence
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for new tickets"))
        print("Set bot presence successfully.")
    except Exception as e:
        print(f"Warning: Could not set bot presence - {e}")
    # Note: Persistent views are complex with Railway's ephemeral filesystem.
    # If the bot restarts, buttons on old messages won't work unless state is stored externally.
    # We are using non-persistent views (default timeout) which is generally safer for Railway.
    print('------ Bot is Ready ------')


@client.event
async def on_guild_channel_create(channel):
    """Called when a new channel is created in a guild the bot is in."""
    if not isinstance(channel, discord.TextChannel): return
    if channel.category_id != TICKET_CATEGORY_ID: return

    print(f"Detected potential ticket channel: #{channel.name} (ID: {channel.id}) in Category ID: {channel.category_id}")
    await asyncio.sleep(1) # Short delay

    guild = channel.guild
    support_role = guild.get_role(SUPPORT_ROLE_ID)

    if not support_role:
        print(f"ERROR: Could not find Support Role with ID {SUPPORT_ROLE_ID} in guild '{guild.name}'. Cannot proceed with permission setup.")
        # Optionally notify channel if possible
        try:
            await channel.send(f"⚠️ **配置错误:** 未找到客服角色 (ID: {SUPPORT_ROLE_ID})，无法自动添加权限。请联系管理员。")
        except discord.Forbidden:
            print(f"Bot lacks permission to send error message in #{channel.name}")
        return # Stop processing for this channel

    try:
        # --- Apply permissions for the support role ---
        overwrite = discord.PermissionOverwrite()
        overwrite.view_channel = True
        overwrite.send_messages = True
        overwrite.read_message_history = True
        overwrite.embed_links = True
        overwrite.attach_files = True
        overwrite.manage_messages = True # Optional: Allow support to manage messages

        await channel.set_permissions(support_role, overwrite=overwrite, reason="Auto-adding support role to new ticket")
        print(f"Successfully applied permissions for role '{support_role.name}' to #{channel.name}")

        # --- Send the message with the button ---
        initial_message_text = (
            f"欢迎来到 Ticket 频道！\n"
            f"负责人 <@&{SUPPORT_ROLE_ID}> 已获得访问权限。\n\n" # Ping the support role
            "**请在开始详细咨询前，点击下方按钮提供一些基本信息：**"
        )
        # Create the view instance
        view = InfoButtonView()
        # Send the message and attach the view (button)
        sent_message = await channel.send(initial_message_text, view=view)
        # Store the message reference in the view for timeout handling
        view.message = sent_message
        print(f"Sent initial message ({sent_message.id}) with info button to #{channel.name}")

    except discord.errors.Forbidden:
        print(f"ERROR: Bot lacks necessary permissions in channel #{channel.name} or category {TICKET_CATEGORY_ID}. Check: 'Manage Roles', 'Send Messages', 'Embed Links', 'View Channel' for the bot's role.")
        # Attempt to send an error message to the channel itself
        try:
            await channel.send(f"⚠️ **权限错误:** 机器人无法为此 Ticket 设置权限或发送初始消息。请检查机器人的服务器权限。")
        except discord.Forbidden:
            pass # If it can't send the initial message, it likely can't send this either.
    except discord.errors.HTTPException as e:
        print(f"ERROR: An Discord API HTTP error occurred: {e.status} - {e.text}")
    except Exception as e:
        print(f"ERROR: An unexpected error occurred in on_guild_channel_create: {e}")
        traceback.print_exc()

# --- Run the Bot ---
if __name__ == "__main__":
    if BOT_TOKEN and SUPPORT_ROLE_ID and TICKET_CATEGORY_ID: # Ensure essential vars are present
        try:
            print("Attempting to run the bot...")
            client.run(BOT_TOKEN)
        except discord.errors.LoginFailure:
            print("CRITICAL ERROR: Invalid Discord Bot Token provided. The bot cannot log in.")
        except discord.errors.PrivilegedIntentsRequired:
             print("CRITICAL ERROR: Privileged intents (like Members or Presence) might be required but are not enabled in the Discord Developer Portal OR in the code's intents object.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to start the bot - {e}")
            traceback.print_exc()
    else:
        print("CRITICAL ERROR: Bot cannot start due to missing configuration (Token, Role ID, or Category ID). Check environment variables.")