import discord
import os
import asyncio
from dotenv import load_dotenv

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
# No message content intent needed for this specific functionality

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Called when the bot successfully connects."""
    print(f'Bot logged in as {client.user}')
    print(f'Monitoring Category ID: {TICKET_CATEGORY_ID}')
    print(f'Adding Support Role ID: {SUPPORT_ROLE_ID}')
    # Set bot presence (optional)
    try:
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for new tickets"))
        print("Set bot presence successfully.")
    except Exception as e:
        print(f"Warning: Could not set bot presence - {e}")
    print('------ Bot is Ready ------')

@client.event
async def on_guild_channel_create(channel):
    """Called when a new channel is created in a guild the bot is in."""
    # 1. Check if it's a text channel
    if not isinstance(channel, discord.TextChannel):
        return # Ignore if not a text channel

    # 2. Check if it's in the designated ticket category
    if channel.category_id != TICKET_CATEGORY_ID:
        # Optional: Log ignored channels for debugging
        # print(f"Ignoring channel #{channel.name} (ID: {channel.id}) - Not in target category {TICKET_CATEGORY_ID}.")
        return # Ignore if not in the target category

    # --- If we reach here, it's likely a new ticket channel ---
    print(f"Detected potential ticket channel: #{channel.name} (ID: {channel.id}) in Category ID: {channel.category_id}")

    # Small delay to potentially avoid race conditions with Ticket Tool's own setup
    await asyncio.sleep(1)

    guild = channel.guild
    support_role = guild.get_role(SUPPORT_ROLE_ID)

    # Validate if the support role was found
    if not support_role:
        print(f"ERROR: Could not find Support Role with ID {SUPPORT_ROLE_ID} in guild '{guild.name}'. Please check the SUPPORT_ROLE_ID variable.")
        # Maybe send a message to the channel indicating the error if bot has send perms?
        # try:
        #     await channel.send(f"⚠️ Configuration Error: Support role (ID: {SUPPORT_ROLE_ID}) not found. Please contact an administrator.")
        # except discord.Forbidden:
        #     pass # Can't send message if role is missing AND bot lacks base perms
        return # Stop processing this channel

    try:
        # --- Apply permissions for the support role ---
        overwrite = discord.PermissionOverwrite()
        overwrite.view_channel = True
        overwrite.send_messages = True
        overwrite.read_message_history = True
        overwrite.embed_links = True
        overwrite.attach_files = True
        overwrite.manage_messages = True # Allows closing/managing ticket messages (Optional but useful for support)

        await channel.set_permissions(support_role, overwrite=overwrite, reason="Auto-adding support role to new ticket")
        print(f"Successfully applied permissions for role '{support_role.name}' to #{channel.name}")

        # --- Send the first "connecting" embed ---
        connecting_embed = discord.Embed(
            description="**<a:loading:123456789012345678> 客服专员正在接入... 请稍候。**\n*Support agent connecting... Please wait.*", # IMPORTANT: Replace 123... with a real loading emoji ID accessible to the bot, or remove it.
            color=0x00BFFF  # Deep Sky Blue
        )
        connecting_embed.set_author(name="[ Support System Interface ]", icon_url="https://i.imgur.com/rRovJxs.png") # Example icon
        connecting_embed.set_footer(text=f"Channel ID: {channel.id} | Status: Routing Request")
        await channel.send(embed=connecting_embed)
        print(f"Sent 'connecting' embed to #{channel.name}")

        # --- Send the second "safe to speak" embed ---
        # Short delay between messages
        await asyncio.sleep(0.5)

        speak_embed = discord.Embed(
            title="💬 **发言区已准备就绪 | Input Area Ready** 💬",
            description=(
                "------------------------------------\n"
                "**您现在可以安全地在下方的聊天框中输入您的问题或请求了。**\n"
                f"(客服人员 <@&{SUPPORT_ROLE_ID}> 已就位)\n\n" # Pings the support role
                "*You may now safely type your question or request in the chat box below.*\n"
                "------------------------------------"
            ),
            color=discord.Color.from_rgb(120, 180, 255) # Soft blue, like an input area highlight
        )
        # Example thumbnail (replace with your preferred one or remove)
        speak_embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/149/149316.png") # Text/message icon
        speak_embed.set_footer(text=f"Ticket: {channel.name} | Status: Awaiting Input")

        await channel.send(embed=speak_embed)
        print(f"Sent 'safe to speak' embed to #{channel.name}")

    except discord.errors.Forbidden:
        print(f"ERROR: Bot lacks necessary permissions in channel #{channel.name} or category {TICKET_CATEGORY_ID}. Check: 'Manage Roles', 'Send Messages', 'Embed Links', 'View Channel' for the bot's role.")
        # Optionally send a message if possible
        try:
            await channel.send(f"⚠️ Permission Error: Bot could not configure support role or send messages. Please check bot permissions.")
        except discord.Forbidden:
            pass # Bot can't even send a basic message here
    except discord.errors.HTTPException as e:
        # Handle potential API errors (like rate limits)
        print(f"ERROR: An Discord API HTTP error occurred: {e.status} - {e.text}")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"ERROR: An unexpected error occurred in on_guild_channel_create: {e}")
        # It might be helpful to log the full traceback here for debugging complex issues
        import traceback
        traceback.print_exc()

# --- Run the Bot ---
if __name__ == "__main__":
    if BOT_TOKEN and SUPPORT_ROLE_ID and TICKET_CATEGORY_ID: # Basic check if vars seem loaded
        try:
            print("Attempting to run the bot...")
            client.run(BOT_TOKEN)
        except discord.errors.LoginFailure:
            print("CRITICAL ERROR: Invalid Discord Bot Token provided. The bot cannot log in.")
        except discord.errors.PrivilegedIntentsRequired:
             print("CRITICAL ERROR: Privileged intents (like Members or Presence) might be required but are not enabled in the Discord Developer Portal OR in the code's intents object.")
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to start the bot - {e}")
            import traceback
            traceback.print_exc()
    else:
        # This case should technically be caught by the initial validation block, but added as a safeguard.
        print("CRITICAL ERROR: Bot cannot start due to missing configuration (Token, Role ID, or Category ID). Check environment variables.")