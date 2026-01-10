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
def home(): return "Bot is Online with Prefix (-)"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ───── 2. إعدادات البوت ─────
TOKEN = os.getenv("TOKEN")
LEVEL_20_ROOM_ID = 1459144630720528437 
intents = discord.Intents.all()
# تم تغيير البريفكس هنا إلى -
bot = commands.Bot(command_prefix="-", intents=intents)

db = sqlite3.connect('levels.db')
cursor = db.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY, 
    xp INTEGER DEFAULT 0, 
    level INTEGER DEFAULT 0,
    custom_role_id INTEGER DEFAULT None
)''')
db.commit()

# ───── 3. التحقق من الإدارة العليا ─────
def is_higher_mgmt():
    async def predicate(ctx):
        role = discord.utils.get(ctx.author.roles, name="〢Higher Managment")
        return role is not None or ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# ───── 4. واجهة الرتب الخاصة ─────
class FriendModal(discord.ui.Modal, title="إضافة صديق لرتبتك"):
    friend_id = discord.ui.TextInput(label="ID الصديق")
    async def on_submit(self, interaction: discord.Interaction):
        try:
            f_id = int(self.friend_id.value)
            cursor.execute("SELECT custom_role_id FROM users WHERE user_id = ?", (interaction.user.id,))
            res = cursor.fetchone()
            if not res or not res[0]: return await interaction.response.send_message("❌ ليس لديك رتبة خاصة!", ephemeral=True)
            role = interaction.guild.get_role(res[0])
            friend = await interaction.guild.fetch_member(f_id)
            await friend.add_roles(role)
            await interaction.response.send_message(f"✅ تمت إضافة {friend.mention} لرتبتك!", ephemeral=True)
        except: await interaction.response.send_message("❌ فشل العثور على العضو", ephemeral=True)

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
                # 1. إنشاء الرتبة مع خاصية الـ hoist لتظهر منفصلة
                role = await interaction.guild.create_role(
                    name=self.name.value, 
                    color=color_val, 
                    hoist=True, 
                    reason="رتبة لفل 20 خاصة"
                )
                
                # 2. محاولة رفع الرتبة تحت رتبة البوت مباشرة ليظهر اللون
                try:
                    bot_role = interaction.guild.me.top_role
                    if bot_role.position > 1:
                        await role.edit(position=bot_role.position - 1)
                except:
                    pass # في حال فشل الترتيب بسبب الصلاحيات لا يتوقف البوت

                await interaction.user.add_roles(role)
                cursor.execute("UPDATE users SET custom_role_id = ? WHERE user_id = ?", (role.id, interaction.user.id))
                db.commit()
                await interaction.response.send_message(f"✅ تم إنشاء رتبتك {role.mention} ورفعها تلقائياً!", ephemeral=True), ephemeral=True)
        except: await interaction.response.send_message("❌ خطأ في اللون أو الصلاحيات", ephemeral=True)

class LevelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="صنع/تعديل رتبة", style=discord.ButtonStyle.green, custom_id="m_role")
    async def m_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (interaction.user.id,))
        res = cursor.fetchone()
        if not res or res[0] < 20: return await interaction.response.send_message("🔒 لفل 20 مطلوب!", ephemeral=True)
        await interaction.response.send_modal(RoleModal())
    
    @discord.ui.button(label="إضافة صديق", style=discord.ButtonStyle.blurple, custom_id="add_f")
    async def add_f(self, interaction: discord.Interaction, button: discord.ui.Button):
        cursor.execute("SELECT level FROM users WHERE user_id = ?", (interaction.user.id,))
        res = cursor.fetchone()
        if not res or res[0] < 20: return await interaction.response.send_message("🔒 لفل 20 مطلوب!", ephemeral=True)
        await interaction.response.send_modal(FriendModal())

# ───── 5. الأحداث (Events) ─────
@bot.event
async def on_ready():
    bot.add_view(LevelView())
    print(f"✅ البوت يعمل بالبريفكس (-) باسم {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.author.id,))
    cursor.execute("UPDATE users SET xp = xp + 15 WHERE user_id = ?", (message.author.id,))
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (message.author.id,))
    xp, level = cursor.fetchone()
    new_lvl = int(0.1 * math.sqrt(xp))
    if new_lvl > level:
        cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_lvl, message.author.id))
        db.commit()
    db.commit()
    await bot.process_commands(message)

# ───── 6. أوامر الإدارة العليا (-) ─────

@bot.command()
@is_higher_mgmt()
async def setlevel(ctx, member: discord.Member, level: int):
    new_xp = int((level / 0.1)**2)
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (member.id,))
    cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (new_xp, level, member.id))
    db.commit()
    await ctx.send(f"✅ تم تعيين مستوى {member.mention} إلى لفل **{level}**")

@bot.command()
@is_higher_mgmt()
async def addxp(ctx, member: discord.Member, amount: int):
    cursor.execute("UPDATE users SET xp = xp + ? WHERE user_id = ?", (amount, member.id))
    cursor.execute("SELECT xp FROM users WHERE user_id = ?", (member.id,))
    new_xp = cursor.fetchone()[0]
    new_lvl = int(0.1 * math.sqrt(new_xp))
    cursor.execute("UPDATE users SET level = ? WHERE user_id = ?", (new_lvl, member.id))
    db.commit()
    await ctx.send(f"✅ تم إضافة {amount} XP لـ {member.mention}")

@bot.command()
@is_higher_mgmt()
async def resetlevel(ctx, member: discord.Member):
    cursor.execute("UPDATE users SET xp = 0, level = 0 WHERE user_id = ?", (member.id,))
    db.commit()
    await ctx.send(f"🧹 تم تصفير بيانات {member.mention}")

# ───── 7. الأوامر العامة (-) ─────

@bot.command()
async def rank(ctx, member: discord.Member = None):
    m = member or ctx.author
    cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (m.id,))
    res = cursor.fetchone()
    if res: await ctx.send(f"📊 **{m.display_name}** | لفل: `{res[1]}` | XP: `{res[0]}`")
    else: await ctx.send("❌ لا بيانات.")

@bot.command(aliases=['lb'])
async def leaderboard(ctx):
    cursor.execute("SELECT user_id, level, xp FROM users ORDER BY xp DESC LIMIT 10")
    data = cursor.fetchall()
    embed = discord.Embed(title="🏆 متصدري السيرفر", color=discord.Color.gold())
    for i, row in enumerate(data, start=1):
        u = bot.get_user(row[0])
        embed.add_field(name=f"#{i} {u.name if u else row[0]}", value=f"لفل: `{row[1]}` | XP: `{row[2]}`", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    if ctx.channel.id != LEVEL_20_ROOM_ID: return
    await ctx.send(embed=discord.Embed(title="✨ رتب خاصة", description="استخدم `-` قبل الأوامر. اصنع رتبتك وأضف أصدقاءك!"), view=LevelView())

# ───── 8. التشغيل ─────
keep_alive()
bot.run(TOKEN)