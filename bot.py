import discord
from discord.ext import commands
import sqlite3
import math
import time
import os
from flask import Flask
from threading import Thread

# ───── السيرفر الوهمي لخداع Render ─────
app = Flask('')

@app.route('/')
def home():
    return "Leveling Bot is Online!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ───── الإعدادات ─────
TOKEN = os.getenv("TOKEN")
LEVEL_20_ROOM_ID = 1459144630720528437 # ضع ID الروم هنا

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ───── قاعدة البيانات ─────
db = sqlite3.connect('levels.db')
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    xp INTEGER DEFAULT 0, 
    level INTEGER DEFAULT 0,
    custom_role_id INTEGER DEFAULT None
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS friends (
    owner_id INTEGER,
    friend_id INTEGER
)''')
db.commit()

voice_times = {}

# ───── نظام الرتب لفل 20 ─────
class RoleModal(discord.ui.Modal, title="تخصيص رتبتك"):
    name = discord.ui.TextInput(label="اسم الرتبة")
    color = discord.ui.TextInput(label="اللون (Hex)", placeholder="#ff0000")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            color_hex = self.color.value.replace("#", "")
            color_val = discord.Color(int(color_hex, 16))
            cursor.execute("SELECT custom_role_id FROM users WHERE user_id = ?", (interaction.user.id,))
            role_id = cursor.fetchone()[0]
            if role_id and interaction.guild.get_role(role_id):
                role = interaction.guild.get_role(role_id)
                await role.edit(name=self.name.value, color=color_val)
                await interaction.response.send_message("✅ تم تحديث رتبتك!", ephemeral=True)
            else:
                role = await interaction.guild.create_role(name=self.name.value, color=color_val)
                await interaction.user.add_roles(role)
                cursor.execute("UPDATE users SET custom_role_id = ? WHERE user_id = ?", (role.id, interaction.user.id))
                db.commit()
                await interaction.response.send_message(f"✅ تم إنشاء رتبة {role.mention} لك!", ephemeral=True)
        except: await interaction.response.send_message("❌ خطأ في اللون!", ephemeral=True)

class LevelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="صنع/تعديل رتبة", style=discord.ButtonStyle.green, custom_id="m_role")
    async def m_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (interaction.user.id,))
        res = cursor.fetchone()
        if not res or res[0] < 20: return await interaction.response.send_message("🔒 لفل 20 مطلوب!", ephemeral=True)
        await interaction.response.send_modal(RoleModal())

# ───── الأحداث ─────
@bot.event
async def on_ready():
    bot.add_view(LevelView())
    print(f"✅ Leveling Bot Ready as {bot.user}")

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
        await message.channel.send(f"🎊 {message.author.mention} ارتقيت للمستوى {new_level}!")
    db.commit()
    await bot.process_commands(message)

# ───── تشغيل ─────
keep_alive()
bot.run(TOKEN)