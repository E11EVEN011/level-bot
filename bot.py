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
def home(): return "Leveling Bot is Alive & Online!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ───── 2. إعدادات البوت ─────
TOKEN = os.getenv("TOKEN")
LEVEL_20_ROOM_ID = 1459144630720528437 # ID الروم الخاص بك
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

# ───── 4. صلاحيات الإدارة العليا ─────
def is_higher_mgmt():
    async def predicate(ctx):
        role = discord.utils.get(ctx.author.roles, name="〢Higher Managment")
        return role is not None or ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# ───── 5. واجهة الرتب الخاصة (لفل 20) ─────
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

# ───── 6. الأحداث (Events) ─────
@bot.event
async def on_ready():
    bot.add_view(LevelView())
    print(f"✅ تم تشغيل البوت: {bot.user}")

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
        await message.channel.send(f"🎊 مبروك {message.author.mention}! وصلت للمستوى **{new_level}**")
    
    db.commit()
    await bot.process_commands(message)

# ───── 7. الأوامر الإدارية (〢Higher Managment) ─────

@bot.command()
@is_higher_mgmt()
async def addxp(ctx, member: discord.Member, amount: int):
    cursor.execute("UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, member.id))
    cursor.execute("SELECT xp FROM users WHERE user_id = ?", (member.id,))
    new_xp = cursor.fetchone()[0]
    new_lvl = int(0.1 * math.sqrt(new_xp))
    cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_lvl, member.id))
    db.commit()
    await ctx.send(f"✅ تم إضافة `{amount}` XP لـ {member.mention}. لفل الحالي: `{new_lvl}`")

@bot.command()
@is_higher_mgmt()
async def setlevel(ctx, member: discord.Member, level: int):
    new_xp = int((level / 0.1)**2)
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
    cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, level, member.id))
    db.commit()
    await ctx.send(f"✅ تم تعيين مستوى {member.mention} إلى لفل **{level}** بنجاح.")

@bot.command()
@is_higher_mgmt()
async def resetlevel(ctx, member: discord.Member):
    cursor.execute("UPDATE users SET xp = 0, level = 0 WHERE user_id = ?", (member.id,))
    db.commit()
    await ctx.send(f"🧹 تم تصفير بيانات {member.mention} بالكامل.")

# ───── 8. الأوامر العامة ─────

@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (member.id,))
    res = cursor.fetchone()
    if res: await ctx.send(f"📊 **{member.display_name}** | لفل: `{res[1]}` | XP: `{res[0]}`")
    else: await ctx.send("❌ لا توجد بيانات لهذا العضو.")

@bot.command(aliases=['lb'])
async def leaderboard(ctx):
    cursor.execute("SELECT user_id, level, xp FROM users ORDER BY xp DESC LIMIT 10")
    data = cursor.fetchall()
    embed = discord.Embed(title="🏆 قائمة المتصدرين", color=discord.Color.gold())
    for i, row in enumerate(data, start=1):
        user = bot.get_user(row[0])
        name = user.name if user else f"عضو غير موجود ({row[0]})"
        embed.add_field(name=f"#{i} {name}", value=f"لفل: `{row[1]}` | XP: `{row[2]}`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    if ctx.channel.id != LEVEL_20_ROOM_ID:
        return await ctx.send(f"❌ هذا الأمر يعمل فقط في الروم المخصص: <#{LEVEL_20_ROOM_ID}>")
    embed = discord.Embed(title="✨ مركز رتب لفل 20", description="حصرياً للمتفاعلين، اضغط الزر بالأسفل لصنع رتبتك الخاصة!", color=discord.Color.blue())
    await ctx.send(embed=embed, view=LevelView())

# ───── 9. التشغيل ─────
keep_alive()
bot.run(TOKEN)