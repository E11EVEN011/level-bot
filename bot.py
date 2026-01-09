import discord
from discord.ext import commands
import sqlite3
import math
import os
import time
from flask import Flask
from threading import Thread

# ───── 1. السيرفر الوهمي (خداع Render) ─────
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive & Online!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ───── 2. إعدادات البوت ─────
TOKEN = os.getenv("TOKEN")
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ───── 3. قاعدة البيانات ─────
db = sqlite3.connect('levels.db')
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    xp INTEGER DEFAULT 0, 
    level INTEGER DEFAULT 0,
    custom_role_id INTEGER DEFAULT None
)''')
db.commit()

# ───── 4. واجهة لفل 20 (النافذة والأزرار) ─────
class RoleModal(discord.ui.Modal, title="تخصيص رتبتك"):
    name = discord.ui.TextInput(label="اسم الرتبة", placeholder="مثلاً: الرهيب")
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
                await interaction.response.send_message("✅ تم تحديث رتبتك بنجاح!", ephemeral=True)
            else:
                role = await interaction.guild.create_role(name=self.name.value, color=color_val)
                await interaction.user.add_roles(role)
                cursor.execute("UPDATE users SET custom_role_id = ? WHERE user_id = ?", (role.id, interaction.user.id))
                db.commit()
                await interaction.response.send_message(f"✅ تم إنشاء رتبة {role.mention} لك!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ خطأ: تأكد من كود اللون الصحيح", ephemeral=True)

class LevelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="صنع/تعديل رتبة", style=discord.ButtonStyle.green, custom_id="m_role_btn")
    async def m_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (interaction.user.id,))
        res = cursor.fetchone()
        lvl = res[0] if res else 0
        if lvl < 20: return await interaction.response.send_message("🔒 تحتاج لفل 20!", ephemeral=True)
        await interaction.response.send_modal(RoleModal())

# ───── 5. الأحداث (Events) ─────
@bot.event
async def on_ready():
    bot.add_view(LevelView())
    print(f"✅ تم تسجيل الدخول باسم {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return

    # نظام الـ XP
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.author.id,))
    cursor.execute("UPDATE users SET xp = xp + 15 WHERE user_id = ?", (message.author.id,))
    
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (message.author.id,))
    xp, level = cursor.fetchone()
    new_level = int(0.1 * math.sqrt(xp))
    
    if new_level > level:
        cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_level, message.author.id))
        db.commit()
        await message.channel.send(f"🎊 مبروك {message.author.mention}! وصلت للمستوى **{new_level}**")
    db.commit()

    # السطر الأهم لعمل الأوامر
    await bot.process_commands(message)

# ───── 6. الأوامر (Commands) ─────

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (member.id,))
    res = cursor.fetchone()
    if res:
        await ctx.send(f"📊 **{member.display_name}** | لفل: `{res[1]}` | خبرة: `{res[0]}`")
    else:
        await ctx.send("❌ لا توجد بيانات لهذا العضو.")

@bot.command(aliases=['lb', 'top'])
async def leaderboard(ctx):
    cursor.execute("SELECT user_id, level, xp FROM users ORDER BY xp DESC LIMIT 10")
    data = cursor.fetchall()
    
    embed = discord.Embed(title="🏆 قائمة متصدري السيرفر", color=discord.Color.gold())
    for i, row in enumerate(data, start=1):
        user = bot.get_user(row[0])
        name = user.name if user else f"عضو غادر ({row[0]})"
        embed.add_field(name=f"#{i} {name}", value=f"لفل: `{row[1]}` | XP: `{row[2]}`", inline=False)
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    embed = discord.Embed(title="✨ مركز رتب لفل 20", description="اضغط الزر لصنع رتبتك الخاصة!", color=discord.Color.blue())
    await ctx.send(embed=embed, view=LevelView())

# ───── 7. التشغيل ─────
keep_alive()
bot.run(TOKEN)