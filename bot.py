import discord
from discord.ext import commands
import sqlite3
import math
import os
from flask import Flask
from threading import Thread

# ───── 1. السيرفر الوهمي ─────
app = Flask('')
@app.route('/')
def home(): return "Leveling Bot is Alive!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    Thread(target=run_flask).start()

# ───── 2. إعدادات البوت ─────
TOKEN = os.getenv("TOKEN")
LEVEL_20_ROOM_ID = 1459144630720528437 
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect('levels.db')
cursor = db.cursor()
cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0, custom_role_id INTEGER DEFAULT None)')
db.commit()

# ───── 3. واجهة الرتب الخاصة ─────

# نافذة إضافة صديق
class FriendModal(discord.ui.Modal, title="إضافة صديق لرتبتك"):
    friend_id = discord.ui.TextInput(label="ID الصديق", placeholder="انسخ الـ ID هنا")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            f_id = int(self.friend_id.value)
            cursor.execute("SELECT custom_role_id FROM users WHERE user_id = ?", (interaction.user.id,))
            res = cursor.fetchone()
            if not res or not res[0]: return await interaction.response.send_message("❌ ليس لديك رتبة خاصة بعد!", ephemeral=True)
            
            role = interaction.guild.get_role(res[0])
            friend = await interaction.guild.fetch_member(f_id)
            await friend.add_roles(role)
            await interaction.response.send_message(f"✅ تمت إضافة {friend.mention} لرتبتك بنجاح!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ تأكد من الـ ID وأن الشخص موجود بالسيرفر", ephemeral=True)

# نافذة صنع الرتبة
class RoleModal(discord.ui.Modal, title="تخصيص رتبتك"):
    name = discord.ui.TextInput(label="اسم الرتبة")
    color = discord.ui.TextInput(label="اللون (Hex)", placeholder="#ff0000")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color_hex = self.color.value.replace("#", "")
            color_val = discord.Color(int(color_hex, 16))
            cursor.execute("SELECT custom_role_id FROM users WHERE user_id = ?", (interaction.user.id,))
            res = cursor.fetchone()
            role_id = res[0] if res else None

            if role_id and interaction.guild.get_role(role_id):
                role = interaction.guild.get_role(role_id)
                await role.edit(name=self.name.value, color=color_val)
                await interaction.response.send_message("✅ تم تحديث رتبتك!", ephemeral=True)
            else:
                # إنشاء الرتبة
                role = await interaction.guild.create_role(name=self.name.value, color=color_val, hoist=True) # hoist تجعلها منفصلة في القائمة
                
                # رفع الرتبة تحت رتبة البوت مباشرة ليظهر اللون
                bot_member = interaction.guild.me
                new_position = bot_member.top_role.position - 1
                await role.edit(position=max(1, new_position))
                
                await interaction.user.add_roles(role)
                cursor.execute("UPDATE users SET custom_role_id = ? WHERE user_id = ?", (role.id, interaction.user.id))
                db.commit()
                await interaction.response.send_message(f"✅ تم إنشاء رتبتك {role.mention} ورفعها في القائمة!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

class LevelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="صنع/تعديل رتبة", style=discord.ButtonStyle.green, custom_id="m_role_btn")
    async def m_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (interaction.user.id,))
        res = cursor.fetchone()
        if not res or res[0] < 20: return await interaction.response.send_message("🔒 تحتاج لفل 20!", ephemeral=True)
        await interaction.response.send_modal(RoleModal())

    @discord.ui.button(label="إضافة صديق", style=discord.ButtonStyle.blurple, custom_id="add_friend_btn")
    async def add_friend_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (interaction.user.id,))
        res = cursor.fetchone()
        if not res or res[0] < 20: return await interaction.response.send_message("🔒 تحتاج لفل 20!", ephemeral=True)
        await interaction.response.send_modal(FriendModal())

# ───── 4. الأحداث والأوامر ─────

@bot.event
async def on_ready():
    bot.add_view(LevelView())
    print(f"✅ {bot.user} Online")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.author.id,))
    cursor.execute("UPDATE users SET xp = xp + 15 WHERE user_id = ?", (message.author.id,))
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (message.author.id,))
    xp, level = cursor.fetchone()
    new_level = int(0.1 * math.sqrt(xp))
    if new_level > level:
        cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, message.author.id))
        db.commit()
    db.commit()
    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    if ctx.channel.id != LEVEL_20_ROOM_ID: return
    embed = discord.Embed(title="✨ مركز رتب لفل 20", description="تحكم برتبتك الخاصة وأضف أصدقائك من هنا!", color=discord.Color.blue())
    await ctx.send(embed=embed, view=LevelView())

# (أضف هنا أوامر addxp, setlevel, rank كما هي في النسخة السابقة)

keep_alive()
bot.run(TOKEN)