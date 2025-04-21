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
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for new tickets"))
    print('------ Bot is Ready ------')

@client.event
async def on_guild_channel_create(channel):
    """Called when a new channel is created in a guild the bot is in."""
    # Check if it's a text channel and in the designated ticket category
    if isinstance(channel, discord.TextChannel) and channel.category_id == TICKET_CATEGORY_ID:
        print(f"Detected new ticket channel: #{channel.name} (ID: {channel.id}) in Category ID: {channel.category_id}")

        # Small delay to potentially avoid race conditions with Ticket Tool's own setup
        await asyncio.sleep(1)

        guild = channel.guild
        support_role = guild.get_role(SUPPORT_ROLE_ID)

        if not support_role:
            print(f"ERROR: Could not find Support Role with ID {SUPPORT_ROLE_ID} in guild '{guild.name}'.")
            return # Stop processing if role not found

        try:
            # Define permissions for the support role
            # Grant essential permissions to manage the ticket
            overwrite = discord.PermissionOverwrite()
            overwrite.view_channel = True
            overwrite.send_messages = True
            overwrite.read_message_history = True
            overwrite.embed_links = True
            overwrite.attach_files = True
            overwrite.manage_messages = True # Allows closing/managing ticket messages

            # Apply the permissions
            await channel.set_permissions(support_role, overwrite=overwrite, reason="Auto-adding support role to new ticket")
            print(f"Successfully applied permissions for role '{support_role.name}' to #{channel.name}")

            # Create the "techy" embed message
            embed = discord.Embed(
                description="**<a:loading:123456789012345678> 客服专员正在接入... 请稍候。**\n*Support agent connecting... Please wait.*", # Replace 123... with a loading emoji ID if you have one
                color=0x00BFFF  # Deep Sky Blue color (adjust as desired)
            )
            # Add a futuristic/system feel
            embed.set_author(name="[ Support System Interface ]", icon_url="https://i.imgur.com/r Rov Jx s.png") # Example icon URL (replace if needed)
            embed.set_footer(text=f"Channel ID: {channel.id} | Status: Routing Request")
            # embed.set_thumbnail(url="URL_TO_YOUR_TECH_ICON") # Optional: Add a relevant thumbnail

            # Send the message
            await channel.send(embed=embed)
            print(f"Sent notification embed to #{channel.name}")

        except discord.errors.Forbidden:
            print(f"ERROR: Bot lacks permissions to modify channel permissions or send messages in #{channel.name}. Check Bot's role permissions and channel/category permissions.")
        except discord.errors.HTTPException as e:
            print(f"ERROR: An HTTP error occurred: {e.status} - {e.text}")
        except Exception as e:
            print(f"ERROR: An unexpected error occurred: {e}")

# --- Run the Bot ---
if __name__ == "__main__":
    try:
        client.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("ERROR: Invalid Discord Bot Token provided. Please check your DISCORD_BOT_TOKEN environment variable.")
    except Exception as e:
        print(f"ERROR: Failed to start the bot - {e}")