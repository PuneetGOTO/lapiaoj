import discord
from discord.ext import commands
from discord import app_commands # For slash commands
import os
import asyncio
from dotenv import load_dotenv
import traceback # Import traceback for better error logging

# --- Configuration ---
load_dotenv() # Load variables from .env file for local testing (optional)

# Get configuration from environment variables (Essential for Railway)
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SUPPORT_ROLE_ID_STR = os.getenv("SUPPORT_ROLE_ID")
TICKET_CATEGORY_ID_STR = os.getenv("TICKET_CATEGORY_ID") # Category for ACTUAL tickets
LOG_CHANNEL_ID_STR = os.getenv("LOG_CHANNEL_ID") # Optional log channel
# NEW: Category for the private channels created for new members
NEW_MEMBER_CATEGORY_ID_STR = os.getenv("NEW_MEMBER_CATEGORY_ID")

# --- Validate Configuration ---
CONFIG_ERROR = False
if not BOT_TOKEN: print("ERROR: DISCORD_BOT_TOKEN missing."); CONFIG_ERROR = True
if not SUPPORT_ROLE_ID_STR: print("ERROR: SUPPORT_ROLE_ID missing."); CONFIG_ERROR = True
if not TICKET_CATEGORY_ID_STR: print("ERROR: TICKET_CATEGORY_ID missing."); CONFIG_ERROR = True
# NEW: Validate the new member category ID
if not NEW_MEMBER_CATEGORY_ID_STR: print("ERROR: NEW_MEMBER_CATEGORY_ID missing. Cannot create welcome channels."); CONFIG_ERROR = True


SUPPORT_ROLE_ID = None
TICKET_CATEGORY_ID = None
LOG_CHANNEL_ID = None # Will be set by command or optional env var
NEW_MEMBER_CATEGORY_ID = None # NEW
try:
    if SUPPORT_ROLE_ID_STR: SUPPORT_ROLE_ID = int(SUPPORT_ROLE_ID_STR)
    if TICKET_CATEGORY_ID_STR: TICKET_CATEGORY_ID = int(TICKET_CATEGORY_ID_STR)
    if LOG_CHANNEL_ID_STR:
        try:
            LOG_CHANNEL_ID = int(LOG_CHANNEL_ID_STR)
        except ValueError:
            print(f"WARNING: LOG_CHANNEL_ID environment variable ('{LOG_CHANNEL_ID_STR}') is not a valid integer. Log channel must be set via command.")
            LOG_CHANNEL_ID = None # Ensure it's None if invalid
    # NEW: Parse the new member category ID
    if NEW_MEMBER_CATEGORY_ID_STR:
        try:
            NEW_MEMBER_CATEGORY_ID = int(NEW_MEMBER_CATEGORY_ID_STR)
        except ValueError:
            print(f"ERROR: NEW_MEMBER_CATEGORY_ID ('{NEW_MEMBER_CATEGORY_ID_STR}') is not a valid integer.")
            CONFIG_ERROR = True # Make this error critical

except ValueError:
    # This catches errors if SUPPORT_ROLE_ID or TICKET_CATEGORY_ID are invalid integers
    print("ERROR: SUPPORT_ROLE_ID or TICKET_CATEGORY_ID environment variable is not a valid integer.")
    CONFIG_ERROR = True # Ensure bot exits if core IDs are invalid

if CONFIG_ERROR:
    exit("Exiting due to configuration errors.")

# --- Bot Setup ---
# IMPORTANT: Enable Members Intent!
intents = discord.Intents.default()
intents.guilds = True
intents.members = True # <<<=== REQUIRED FOR on_member_join

bot = commands.Bot(command_prefix="!", intents=intents) # Prefix needed for Bot class, but we use slash commands

# --- In-Memory Storage ---
# WARNING: This data is lost on bot restart!
ticket_data_cache = {}

# Store the log channel ID (can be updated by command)
# Initialize with value from env var if provided and valid
bot.log_channel_id = LOG_CHANNEL_ID

# --- Modal Definition ---
class InfoModal(discord.ui.Modal, title='请提供必要信息以处理您的请求'):
    identifier = discord.ui.TextInput(
        label='角色ID 或 个人资料链接 (用于身份确认)',
        style=discord.TextStyle.short,
        placeholder='请提供相关ID或链接',
        required=True,
        max_length=150
    )
    reason = discord.ui.TextInput(
        label='请说明来意 (Reason for contact)',
        style=discord.TextStyle.paragraph,
        placeholder='例如：申请GJ正式成员/GJZ精英部队/GJK前鋒部队/合作/或其他...',
        required=True,
        max_length=1000
    )
    kill_count = discord.ui.TextInput(
        label='(如果适用) 你大概多少杀？',
        style=discord.TextStyle.short,
        placeholder='例如：50+ (若不适用可填 N/A)',
        required=False, # Optional
        max_length=50
    )
    notes = discord.ui.TextInput(
        label='其他补充说明 (Optional Notes)',
        style=discord.TextStyle.paragraph,
        placeholder='任何其他需要让客服知道的信息...',
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user
        channel_id = interaction.channel_id

        # Store the submitted data in the cache
        submitted_data = {
            "user_id": user.id,
            "user_mention": user.mention,
            "user_name": str(user),
            "identifier": self.identifier.value,
            "reason": self.reason.value,
            "kill_count": self.kill_count.value if self.kill_count.value else "N/A",
            "notes": self.notes.value if self.notes.value else "无",
            "channel_name": interaction.channel.name,
            "channel_mention": interaction.channel.mention, # Store mention for logging
            "submission_time": discord.utils.utcnow()
        }
        ticket_data_cache[channel_id] = submitted_data
        print(f"Stored data for ticket channel {channel_id}")

        # Send confirmation embed in the ticket channel
        confirm_embed = discord.Embed(
            title="📄 信息已提交，等待客服审核",
            description=(
                f"感谢 {user.mention} 提供信息！\n"
                f"客服人员 <@&{SUPPORT_ROLE_ID}> 将会审核您的请求。\n\n"
                "**请耐心等待，客服人员审核完毕后会在此频道进行确认。**"
            ),
            color=discord.Color.orange()
        )
        confirm_embed.add_field(name="身份标识 (供参考)", value=self.identifier.value, inline=False)
        confirm_embed.add_field(name="来意说明 (供参考)", value=self.reason.value, inline=False)
        confirm_embed.set_footer(text=f"Ticket: {interaction.channel.name} | Status: Pending Verification")

        await interaction.channel.send(embed=confirm_embed)
        await interaction.response.send_message("✅ 你的信息已提交，请等待客服审核。", ephemeral=True, delete_after=20)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Error in InfoModal submission: {error}")
        traceback.print_exc()
        await interaction.response.send_message('提交信息时发生错误，请稍后重试或联系管理员。', ephemeral=True)


# --- View Definition ---
class InfoButtonView(discord.ui.View):
    def __init__(self, *, timeout=300): # Increased timeout
        super().__init__(timeout=timeout)
        self.message = None

    @discord.ui.button(label="📝 提供信息 (Provide Info)", style=discord.ButtonStyle.primary, custom_id="provide_ticket_info_v2")
    async def provide_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = InfoModal()
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        print(f"InfoButtonView for message {self.message.id if self.message else 'Unknown'} timed out.")
        self.provide_info_button.disabled = True
        if self.message:
            try: await self.message.edit(content="*此信息收集按钮已过期。*", view=self)
            except Exception as e: print(f"Error editing message on view timeout: {e}")
        self.stop()


# --- Bot Events ---
@bot.event
async def on_ready():
    print(f'Bot logged in as {bot.user}')
    print(f'Monitoring Ticket Category ID: {TICKET_CATEGORY_ID}')
    print(f'Support Role ID: {SUPPORT_ROLE_ID}')
    if bot.log_channel_id:
        print(f'Logging Channel ID: {bot.log_channel_id}')
    else:
        print('Logging Channel not set. Use /setlogchannel command.')
    # NEW: Print new member category
    if NEW_MEMBER_CATEGORY_ID:
        print(f'New Member Welcome Category ID: {NEW_MEMBER_CATEGORY_ID}')
    else:
        # This case should be caught by validation now, but good for clarity
        print('ERROR: New Member Welcome Category ID not set/invalid. Welcome channel feature disabled.')

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Error syncing slash commands: {e}")
        traceback.print_exc()
    try:
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="new members & tickets"))
        print("Set bot presence successfully.")
    except Exception as e:
        print(f"Warning: Could not set bot presence - {e}")

    print('------ Bot is Ready ------')

@bot.event
async def on_guild_channel_create(channel):
    """Handle new channel creation for ACTUAL tickets (from Ticket Tool)."""
    if not isinstance(channel, discord.TextChannel): return
    # Check against ACTUAL ticket category ID
    if channel.category_id != TICKET_CATEGORY_ID: return

    print(f"Detected potential ticket channel: #{channel.name} (ID: {channel.id})")
    await asyncio.sleep(1)
    guild = channel.guild
    support_role = guild.get_role(SUPPORT_ROLE_ID)
    if not support_role:
        print(f"ERROR: Support Role ID {SUPPORT_ROLE_ID} not found.")
        # Maybe send a message to the channel if possible?
        try: await channel.send(f"⚠️ **配置错误:** 未找到客服角色 (ID: {SUPPORT_ROLE_ID})。")
        except discord.Forbidden: pass
        return # Don't proceed if support role isn't found

    try:
        # Apply permissions for support role
        overwrite = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, embed_links=True, attach_files=True, manage_messages=True)
        await channel.set_permissions(support_role, overwrite=overwrite, reason="Auto-adding support role to ticket")
        print(f"Applied permissions for role '{support_role.name}' to ticket #{channel.name}")

        # Send the message with the info collection button
        initial_message_text = f"欢迎！负责人 <@&{SUPPORT_ROLE_ID}> 已就绪。\n**请点击下方按钮提供必要信息以开始处理您的请求：**"
        view = InfoButtonView()
        sent_message = await channel.send(initial_message_text, view=view)
        view.message = sent_message # Store message ref for timeout handling
        print(f"Sent initial message ({sent_message.id}) with info button to ticket #{channel.name}")

    except discord.errors.Forbidden:
        print(f"ERROR: Bot lacks permissions (Manage Roles/Send Messages?) in ticket channel #{channel.name}.")
        try: await channel.send(f"⚠️ **权限错误:** 机器人无法设置权限或发送消息。")
        except discord.Forbidden: pass
    except Exception as e:
        print(f"ERROR in on_guild_channel_create: {e}")
        traceback.print_exc()


# --- NEW: Event handler for new members joining ---
@bot.event
async def on_member_join(member: discord.Member):
    """Handles new members joining the server."""
    # Ensure NEW_MEMBER_CATEGORY_ID is loaded and valid
    if not NEW_MEMBER_CATEGORY_ID:
        print(f"Member {member.name} joined, but NEW_MEMBER_CATEGORY_ID is not configured. Skipping welcome channel.")
        return

    guild = member.guild
    support_role = guild.get_role(SUPPORT_ROLE_ID)
    welcome_category = guild.get_channel(NEW_MEMBER_CATEGORY_ID)

    # Double check components before proceeding
    if not support_role:
        print(f"ERROR: Support Role {SUPPORT_ROLE_ID} not found. Cannot create welcome channel for {member.name}.")
        return
    if not welcome_category or not isinstance(welcome_category, discord.CategoryChannel):
        print(f"ERROR: New Member Category {NEW_MEMBER_CATEGORY_ID} not found or isn't a category. Cannot create welcome channel for {member.name}.")
        return

    print(f"New member joined: {member.name} ({member.id}). Attempting to create welcome channel...")

    # Permissions for the private welcome channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False), # Hide from @everyone
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, embed_links=True, attach_files=True), # Allow member
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_permissions=True), # Allow bot
        support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True) # Allow support
    }

    # Sanitize member name for channel name (basic example)
    safe_name = "".join(c for c in member.name if c.isalnum() or c in ['-', '_']).lower() or "member"
    channel_name = f"welcome-{safe_name[:80]}" # Limit length

    try:
        welcome_channel = await guild.create_text_channel(
            name=channel_name,
            category=welcome_category,
            overwrites=overwrites,
            topic=f"引导新成员 {member.display_name} 进行验证 | Welcome channel for {member.display_name}",
            reason=f"自动为新成员 {member.name} 创建引导频道"
        )
        print(f"Successfully created welcome channel #{welcome_channel.name} (ID: {welcome_channel.id}) for {member.name}")
    except discord.Forbidden:
        print(f"ERROR: Bot lacks permissions (Manage Channels/Roles?) to create welcome channel for {member.name} in category {NEW_MEMBER_CATEGORY_ID}.")
        # Consider logging this to a specific admin/log channel if possible
        return
    except Exception as e:
        print(f"ERROR: Failed to create welcome channel for {member.name}: {e}")
        traceback.print_exc()
        return

    # Send the guidance message
    try:
        # --- !!! IMPORTANT: EDIT THE CHANNEL NAME BELOW !!! ---
        ticket_panel_channel_name = "#频道名-客服中心验证" # <<<=== REPLACE THIS WITH YOUR ACTUAL TICKET PANEL CHANNEL NAME!!!
        # --- !!! IMPORTANT: EDIT THE CHANNEL NAME ABOVE !!! ---

        guidance_message = (
            f"欢迎 {member.mention} 加入 **{guild.name}**！🎉\n\n"
            f"为了确保服务器环境和成员权益，我们需要您先完成身份验证。\n\n"
            f"➡️ **请前往 `{ticket_panel_channel_name}` 频道，点击那里的 'Create Ticket' 按钮来开始正式的验证流程。**\n\n"
            f"我们的客服团队 <@&{SUPPORT_ROLE_ID}> 已经收到通知，会尽快协助您完成验证。\n"
            f"如果在 `{ticket_panel_channel_name}` 遇到问题，您可以在此频道简单说明，客服人员会看到。"
        )

        await welcome_channel.send(guidance_message)
        print(f"Sent welcome message to #{welcome_channel.name} for {member.name}")

    except discord.Forbidden:
        print(f"ERROR: Bot lacks permission to send messages in the created welcome channel #{welcome_channel.name}.")
    except Exception as e:
        print(f"ERROR: Failed to send welcome message for {member.name}: {e}")
        traceback.print_exc()


# --- Slash Commands ---
# Command: /setlogchannel
@bot.tree.command(name="setlogchannel", description="设置用于记录已验证用户信息的频道。")
@app_commands.describe(channel="选择要发送日志的文本频道")
@app_commands.checks.has_permissions(administrator=True)
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.log_channel_id = channel.id
    print(f"Log channel set to: #{channel.name} (ID: {channel.id}) by {interaction.user}")
    await interaction.response.send_message(f"✅ 记录频道已设置为 {channel.mention}。\n**提示:** 此设置在机器人重启后会丢失，建议设置 `LOG_CHANNEL_ID` 环境变量。", ephemeral=True)

@set_log_channel.error
async def set_log_channel_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ 你没有管理员权限。", ephemeral=True)
    else:
        print(f"Error in /setlogchannel: {error}")
        traceback.print_exc()
        await interaction.response.send_message("设置记录频道时发生未知错误。", ephemeral=True)

# Check function for ticket category
def is_in_ticket_category():
    async def predicate(interaction: discord.Interaction) -> bool:
        if TICKET_CATEGORY_ID is None: return False
        # Check if channel exists and has a category attribute
        if interaction.channel and hasattr(interaction.channel, 'category_id'):
            return interaction.channel.category_id == TICKET_CATEGORY_ID
        return False # Not a channel with a category or channel doesn't exist
    return app_commands.check(predicate)

# Command: /verifyticket
@bot.tree.command(name="verifyticket", description="确认当前 Ticket 用户身份已验证，并记录信息。")
@is_in_ticket_category() # Check if command is used in the correct category
@app_commands.checks.has_role(SUPPORT_ROLE_ID) # Check if user has the support role
async def verify_ticket(interaction: discord.Interaction):
    channel_id = interaction.channel_id

    # 1. Check log channel
    if not bot.log_channel_id:
        await interaction.response.send_message("❌ **错误:** 未设置记录频道。请管理员使用 `/setlogchannel` 命令。", ephemeral=True)
        return

    # 2. Retrieve data from cache
    data_to_log = ticket_data_cache.get(channel_id)
    if not data_to_log:
        await interaction.response.send_message("❌ **错误:** 未找到此 Ticket 的初始信息 (可能未提交或已丢失)。", ephemeral=True)
        return

    # 3. Get log channel object
    log_channel = bot.get_channel(bot.log_channel_id)
    if not log_channel or not isinstance(log_channel, discord.TextChannel):
        await interaction.response.send_message(f"❌ **错误:** 无法找到有效的记录频道 (ID: `{bot.log_channel_id}`)。", ephemeral=True)
        return

    # 4. Format log embed
    log_embed = discord.Embed(
        title=f"✅ Ticket 已验证 | 用户信息记录",
        description=f"Ticket 频道: {data_to_log.get('channel_mention', f'<#{channel_id}>')} (`{channel_id}`)",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )
    log_embed.add_field(name="验证处理人", value=interaction.user.mention, inline=False)
    log_embed.add_field(name="用户信息", value=f"{data_to_log['user_mention']} (`{data_to_log['user_id']}`)", inline=False)
    log_embed.add_field(name="提交的身份标识 (ID/链接)", value=data_to_log['identifier'], inline=False)
    log_embed.add_field(name="提交的来意说明", value=data_to_log['reason'], inline=False)
    if data_to_log['kill_count'] != "N/A": log_embed.add_field(name="提交的大致击杀数", value=data_to_log['kill_count'], inline=True)
    if data_to_log['notes'] != "无": log_embed.add_field(name="提交的补充说明", value=data_to_log['notes'], inline=False)
    log_embed.set_footer(text=f"原始提交时间: {data_to_log['submission_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    try: # Try to add user avatar
        user_obj = bot.get_user(data_to_log['user_id']) or await bot.fetch_user(data_to_log['user_id'])
        if user_obj: log_embed.set_thumbnail(url=user_obj.display_avatar.url)
    except Exception as avatar_error: print(f"Could not fetch avatar for user {data_to_log['user_id']}: {avatar_error}")

    # 5. Send log
    try:
        await log_channel.send(embed=log_embed)
        print(f"Logged verification for ticket {channel_id} to channel {bot.log_channel_id}")
    except discord.Forbidden: await interaction.response.send_message(f"❌ **错误:** 机器人无权向记录频道 {log_channel.mention} 发送消息。", ephemeral=True); return
    except Exception as e: print(f"Error sending log message: {e}"); traceback.print_exc(); await interaction.response.send_message(f"❌ **错误:** 发送日志到记录频道时出错。", ephemeral=True); return

    # 6. Send confirmation in ticket channel
    await interaction.response.send_message(f"✅ **验证完成！** {interaction.user.mention} 已确认此 Ticket 的用户身份，相关信息已记录。")

    # 7. Clean up cache
    if channel_id in ticket_data_cache:
        del ticket_data_cache[channel_id]
        print(f"Removed cached data for ticket channel {channel_id}")

@verify_ticket.error
async def verify_ticket_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
     if isinstance(error, app_commands.CheckFailure): await interaction.response.send_message("❌ 此命令只能由指定客服人员在有效的 Ticket 分类频道中使用。", ephemeral=True)
     elif isinstance(error, app_commands.MissingRole): await interaction.response.send_message("❌ 你没有所需的客服角色来使用此命令。", ephemeral=True)
     else: print(f"Error in /verifyticket: {error}"); traceback.print_exc(); await interaction.response.send_message("处理验证命令时发生未知错误。", ephemeral=True)

# --- Run the Bot ---
if __name__ == "__main__":
    # Check if all *required* IDs are loaded before starting
    if BOT_TOKEN and SUPPORT_ROLE_ID and TICKET_CATEGORY_ID and NEW_MEMBER_CATEGORY_ID:
        try:
            print("Attempting to run the bot...")
            bot.run(BOT_TOKEN)
        except discord.errors.LoginFailure: print("CRITICAL ERROR: Invalid Discord Bot Token provided.")
        except discord.errors.PrivilegedIntentsRequired: print("CRITICAL ERROR: Privileged Gateway Intents ('Members') are required but not enabled in the Discord Developer Portal.")
        except Exception as e: print(f"CRITICAL ERROR: Failed to start the bot - {e}"); traceback.print_exc()
    else:
        print("CRITICAL ERROR: Bot cannot start due to missing core configuration (Token, Role ID, Ticket Category ID, or New Member Category ID). Check environment variables.")