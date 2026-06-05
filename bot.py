import os, json, requests, random, string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ─── CONFIG ──────────────────────────────────────────────────
BOT_TOKEN   = os.environ.get("BOT_TOKEN", "8726110607:AAE0EYK8V_wr0T5fE2vHIeXTBtZXD85SNyg")
ADMIN_IDS   = list(map(int, os.environ.get("ADMIN_IDS", "6548871396").split(",")))
RENDER_URL  = os.environ.get("RENDER_URL", "https://poscus-predicter.onrender.com")
ADMIN_TOKEN = "VC5SA9AT0H2010"
HEADERS     = {"Content-Type": "application/json", "X-Admin-Token": ADMIN_TOKEN}

# ─── STATES ──────────────────────────────────────────────────
(WAIT_KEY, WAIT_NAME, WAIT_EXPIRY, WAIT_NOTE,
 WAIT_DEL_KEY, WAIT_RESET_KEY, WAIT_SEARCH,
 WAIT_BULK_COUNT, WAIT_BULK_PREFIX, WAIT_BULK_DAYS,
 # Reseller states
 WAIT_RES_ID, WAIT_RES_NAME, WAIT_RES_NOTE, WAIT_RES_DEL,
 # Reseller user states
 WAIT_R_DEVICE_ID, WAIT_R_DEVICE_NAME, WAIT_R_KEY, WAIT_R_EXPIRY_CONFIRM,
 WAIT_R_DEL_KEY
) = range(19)

# ─── API HELPERS ─────────────────────────────────────────────
def api_get(path, headers=None):
    h = headers or HEADERS
    r = requests.get(f"{RENDER_URL}{path}", headers=h, timeout=10)
    return r.json()

def api_post(path, data, headers=None):
    h = headers or HEADERS
    r = requests.post(f"{RENDER_URL}{path}", json=data, headers=h, timeout=10)
    return r.json()

def res_headers(token):
    return {"Content-Type": "application/json", "X-Reseller-Token": token}

def gen_key(prefix="PC", length=8):
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return prefix + "".join(random.choices(chars, k=length))

def fmt_date(hours=None, days=None):
    if hours:
        return (datetime.now() + timedelta(hours=hours)).strftime('%Y-%m-%d')
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

def is_admin(uid): return uid in ADMIN_IDS

def get_status(k):
    today = datetime.now().strftime('%Y-%m-%d')
    if k.get('expiry') and k['expiry'] < today: return '🟠 EXPIRED'
    return '🟢 ACTIVE' if k.get('active') else '🔴 INACTIVE'

# ─── MARKOV / REPLY KEYBOARDS ────────────────────────────────
def admin_main_kb():
    """Reply keyboard for admin main menu"""
    return ReplyKeyboardMarkup([
        ["➕ Add Key",    "📋 All Keys"],
        ["🔍 Search Key", "🗑️ Delete Key"],
        ["📱 Reset Device","⚡ Bulk Generate"],
        ["👥 Resellers",  "📊 Stats"],
        ["🗑️ Del Expired","❌ Deact All"],
    ], resize_keyboard=True)

def reseller_main_kb():
    """Reply keyboard for reseller main menu"""
    return ReplyKeyboardMarkup([
        ["📱 My Devices", "➕ Add Device"],
        ["🗑️ Remove Device", "📊 My Stats"],
        ["🔙 Exit"],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)

# ─── INLINE KEYBOARDS ────────────────────────────────────────
def expiry_inline_kb(prefix="exp"):
    """Expiry inline buttons: 1h 2h 5h 12h 1d 3d 7d 15d 30d 60d"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 Hour",   callback_data=f"{prefix}_h1"),
         InlineKeyboardButton("2 Hours",  callback_data=f"{prefix}_h2"),
         InlineKeyboardButton("5 Hours",  callback_data=f"{prefix}_h5")],
        [InlineKeyboardButton("12 Hours", callback_data=f"{prefix}_h12"),
         InlineKeyboardButton("1 Day",    callback_data=f"{prefix}_d1"),
         InlineKeyboardButton("3 Days",   callback_data=f"{prefix}_d3")],
        [InlineKeyboardButton("7 Days",   callback_data=f"{prefix}_d7"),
         InlineKeyboardButton("15 Days",  callback_data=f"{prefix}_d15"),
         InlineKeyboardButton("30 Days",  callback_data=f"{prefix}_d30")],
        [InlineKeyboardButton("60 Days",  callback_data=f"{prefix}_d60"),
         InlineKeyboardButton("Lifetime ♾️", callback_data=f"{prefix}_d0")],
    ])

def parse_expiry_cb(data, prefix="exp"):
    """Parse expiry callback → return (display_text, date_str)"""
    val = data.replace(f"{prefix}_", "")
    if val == "d0": return "♾️ Lifetime", ""
    if val.startswith("h"):
        h = int(val[1:])
        return f"{h} Hour{'s' if h>1 else ''}", fmt_date(hours=h)
    if val.startswith("d"):
        d = int(val[1:])
        return f"{d} Day{'s' if d>1 else ''}", fmt_date(days=d)
    return "Unknown", ""

def main_menu_inline():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="back")]
    ])

# ═══════════════════════════════════════════════════════════════
# ADMIN SECTION
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ctx.user_data.clear()

    # Check if this is a reseller
    resellers_raw = api_get('/api/admin/resellers')
    reseller_info = None
    for rid, rd in resellers_raw.items():
        if str(rd.get("tg_id","")) == str(uid):
            reseller_info = (rid, rd)
            break

    if is_admin(uid):
        await update.message.reply_text(
            f"🐉 *POSCUS ADMIN BOT*\n\n"
            f"Welcome back, `{update.effective_user.first_name}`!\n"
            f"🌐 `{RENDER_URL}`",
            parse_mode='Markdown',
            reply_markup=admin_main_kb()
        )
        ctx.user_data['role'] = 'admin'
        return ConversationHandler.END

    if reseller_info:
        rid, rd = reseller_info
        ctx.user_data['role'] = 'reseller'
        ctx.user_data['res_id'] = rid
        ctx.user_data['res_token'] = rd['token']
        await update.message.reply_text(
            f"👥 *RESELLER PANEL*\n\n"
            f"Welcome, `{rd.get('name', rid)}`!\n"
            f"🆔 Your ID: `{rid}`",
            parse_mode='Markdown',
            reply_markup=reseller_main_kb()
        )
        return ConversationHandler.END

    await update.message.reply_text("⛔ Access denied! Contact admin.")
    return ConversationHandler.END

# ─── ADMIN: STATS ────────────────────────────────────────────
async def show_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        keys = api_get('/api/admin/keys')
        today = datetime.now().strftime('%Y-%m-%d')
        total = len(keys)
        active = sum(1 for k in keys.values() if k.get('active') and (not k.get('expiry') or k['expiry'] >= today))
        inactive = sum(1 for k in keys.values() if not k.get('active'))
        expired = sum(1 for k in keys.values() if k.get('expiry') and k['expiry'] < today)
        locked = sum(1 for k in keys.values() if k.get('device','').strip())
        resellers = api_get('/api/admin/resellers')
        text = (
            f"📊 *POSCUS STATS*\n\n"
            f"🔑 Total Keys: `{total}`\n"
            f"🟢 Active: `{active}`\n"
            f"🔴 Inactive: `{inactive}`\n"
            f"🟠 Expired: `{expired}`\n"
            f"📱 Device Locked: `{locked}`\n"
            f"👥 Resellers: `{len(resellers)}`\n\n"
            f"🌐 {RENDER_URL}"
        )
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())

# ─── ADMIN: ALL KEYS ─────────────────────────────────────────
async def show_all_keys(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        keys = api_get('/api/admin/keys')
        if not keys:
            await update.message.reply_text("📭 No keys found!", reply_markup=admin_main_kb())
            return
        lines = ["🔑 *ALL KEYS*\n"]
        for kid, kd in list(keys.items())[:30]:
            st = get_status(kd)
            nm = kd.get('name','?')
            ex = kd.get('expiry','♾️')
            dev = '📱' if kd.get('device','').strip() else '🆓'
            owner = kd.get('owner','admin')
            lines.append(f"{st} {dev} `{kid}`\n👤 {nm} | ⏰ {ex} | 🏷 {owner}")
        if len(keys) > 30:
            lines.append(f"\n...and {len(keys)-30} more")
        await update.message.reply_text('\n'.join(lines), parse_mode='Markdown', reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())

# ─── ADMIN: ADD KEY ──────────────────────────────────────────
async def add_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['flow'] = 'add_key'
    ctx.user_data['auto_key'] = gen_key()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🎲 Auto: {ctx.user_data['auto_key']}", callback_data="use_auto_key")],
        [InlineKeyboardButton("✏️ Type Custom Key", callback_data="type_custom_key")],
    ])
    await update.message.reply_text("➕ *ADD NEW KEY*\n\nChoose key type:", parse_mode='Markdown', reply_markup=kb)
    return WAIT_KEY

async def use_auto_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    ctx.user_data['key'] = ctx.user_data['auto_key']
    await q.edit_message_text(f"✅ Key: `{ctx.user_data['key']}`\n\n👤 Send *user name* (or type skip):", parse_mode='Markdown')
    return WAIT_NAME

async def type_custom_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("✏️ Send the custom key ID:")
    return WAIT_KEY

async def recv_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['key'] = update.message.text.strip().upper()
    await update.message.reply_text(f"✅ Key: `{ctx.user_data['key']}`\n\n👤 Send *user name* (or type skip):", parse_mode='Markdown')
    return WAIT_NAME

async def recv_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    ctx.user_data['name'] = '' if txt.lower() in ['skip','/skip'] else txt
    await update.message.reply_text("⏰ *Select expiry:*", parse_mode='Markdown', reply_markup=expiry_inline_kb("exp"))
    return WAIT_EXPIRY

async def recv_expiry_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not q.data.startswith("exp_"): return WAIT_EXPIRY
    label, date = parse_expiry_cb(q.data, "exp")
    ctx.user_data['expiry'] = date
    ctx.user_data['expiry_label'] = label
    await q.edit_message_text(f"⏰ Expiry: *{label}*\n\n📝 Send *note* (or type skip):", parse_mode='Markdown')
    return WAIT_NOTE

async def recv_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    ctx.user_data['note'] = '' if txt.lower() in ['skip','/skip'] else txt
    payload = {
        'key': ctx.user_data['key'],
        'name': ctx.user_data.get('name',''),
        'expiry': ctx.user_data.get('expiry',''),
        'note': ctx.user_data.get('note',''),
        'active': True, 'device': ''
    }
    try:
        r = api_post('/api/admin/key/add', payload)
        if r.get('ok'):
            await update.message.reply_text(
                f"✅ *KEY ADDED!*\n\n"
                f"🔑 Key: `{ctx.user_data['key']}`\n"
                f"👤 Name: {ctx.user_data.get('name','—')}\n"
                f"⏰ Expiry: {ctx.user_data.get('expiry_label','♾️ Lifetime')}\n"
                f"📝 Note: {ctx.user_data.get('note','—')}\n\n"
                f"Share key with user! 🎉",
                parse_mode='Markdown', reply_markup=admin_main_kb()
            )
        else:
            await update.message.reply_text(f"❌ {r.get('msg','Error')}", reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())
    ctx.user_data.clear()
    return ConversationHandler.END

# ─── ADMIN: SEARCH ───────────────────────────────────────────
async def search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Send *key ID* or *user name* to search:", parse_mode='Markdown', reply_markup=cancel_kb())
    return WAIT_SEARCH

async def recv_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "❌ Cancel":
        await update.message.reply_text("❌ Cancelled.", reply_markup=admin_main_kb())
        return ConversationHandler.END
    query = update.message.text.strip().upper()
    try:
        keys = api_get('/api/admin/keys')
        results = {k:v for k,v in keys.items() if query in k or query.lower() in (v.get('name','').lower())}
        if not results:
            await update.message.reply_text("❌ No keys found!", reply_markup=admin_main_kb())
            return ConversationHandler.END
        lines = [f"🔍 *SEARCH: {query}*\n"]
        for kid, kd in results.items():
            st = get_status(kd)
            nm = kd.get('name','?')
            ex = kd.get('expiry','♾️')
            dev = kd.get('device','')
            dev_short = dev[:20]+'...' if len(dev)>20 else (dev or '—')
            lines.append(f"{st} `{kid}`\n👤 {nm} | ⏰ {ex}\n📱 {dev_short}\n")
        await update.message.reply_text('\n'.join(lines), parse_mode='Markdown', reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())
    return ConversationHandler.END

# ─── ADMIN: DELETE KEY ───────────────────────────────────────
async def del_key_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗑️ Send *key ID* to delete:", parse_mode='Markdown', reply_markup=cancel_kb())
    return WAIT_DEL_KEY

async def recv_del_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "❌ Cancel":
        await update.message.reply_text("❌ Cancelled.", reply_markup=admin_main_kb())
        return ConversationHandler.END
    kid = update.message.text.strip().upper()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_del_{kid}"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_inline")]
    ])
    await update.message.reply_text(f"⚠️ Delete key `{kid}`?", parse_mode='Markdown', reply_markup=kb)
    return ConversationHandler.END

async def confirm_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    kid = q.data.replace('confirm_del_','')
    try:
        api_post('/api/admin/key/delete', {'key': kid})
        await q.edit_message_text(f"✅ Key `{kid}` deleted!", parse_mode='Markdown')
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")

# ─── ADMIN: RESET DEVICE ─────────────────────────────────────
async def reset_dev_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 Send *key ID* to reset device:", parse_mode='Markdown', reply_markup=cancel_kb())
    return WAIT_RESET_KEY

async def recv_reset_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "❌ Cancel":
        await update.message.reply_text("❌ Cancelled.", reply_markup=admin_main_kb())
        return ConversationHandler.END
    kid = update.message.text.strip().upper()
    try:
        api_post('/api/admin/key/reset-device', {'key': kid})
        await update.message.reply_text(
            f"✅ Device reset for `{kid}`!\nUser can login on new device. 📱",
            parse_mode='Markdown', reply_markup=admin_main_kb()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())
    return ConversationHandler.END

# ─── ADMIN: BULK GENERATE ────────────────────────────────────
async def bulk_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("⚡ *BULK GENERATE*\n\nSend prefix (e.g. VIP, PC) or type skip:", parse_mode='Markdown', reply_markup=cancel_kb())
    return WAIT_BULK_PREFIX

async def recv_bulk_prefix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "❌ Cancel":
        await update.message.reply_text("❌ Cancelled.", reply_markup=admin_main_kb())
        return ConversationHandler.END
    txt = update.message.text.strip().upper()
    ctx.user_data['prefix'] = 'PC' if txt in ['SKIP','/SKIP'] else txt
    await update.message.reply_text("🔢 How many keys? (1-50):", reply_markup=cancel_kb())
    return WAIT_BULK_COUNT

async def recv_bulk_count(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "❌ Cancel":
        await update.message.reply_text("❌ Cancelled.", reply_markup=admin_main_kb())
        return ConversationHandler.END
    try:
        n = min(50, max(1, int(update.message.text.strip())))
        ctx.user_data['count'] = n
    except:
        await update.message.reply_text("❌ Enter a number 1-50:")
        return WAIT_BULK_COUNT
    await update.message.reply_text("⏰ *Select expiry for all keys:*", parse_mode='Markdown', reply_markup=expiry_inline_kb("bexp"))
    return WAIT_BULK_DAYS

async def recv_bulk_days(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not q.data.startswith("bexp_"): return WAIT_BULK_DAYS
    label, expiry = parse_expiry_cb(q.data, "bexp")
    prefix = ctx.user_data.get('prefix','PC')
    count = ctx.user_data.get('count',5)
    await q.edit_message_text(f"⏳ Generating {count} keys...")
    generated = []
    for _ in range(count):
        key = gen_key(prefix)
        api_post('/api/admin/key/add', {'key':key,'active':True,'device':'','expiry':expiry,'name':'','note':''})
        generated.append(key)
    keys_text = '\n'.join([f'`{k}`' for k in generated])
    await q.edit_message_text(
        f"✅ *{count} KEYS GENERATED!*\n⏰ Expiry: {label}\n\n{keys_text}",
        parse_mode='Markdown'
    )
    ctx.user_data.clear()
    return ConversationHandler.END

# ─── ADMIN: BULK ACTIONS ─────────────────────────────────────
async def del_expired(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        keys = api_get('/api/admin/keys')
        today = datetime.now().strftime('%Y-%m-%d')
        expired = [k for k,v in keys.items() if v.get('expiry') and v['expiry'] < today]
        if not expired:
            await update.message.reply_text("✅ No expired keys!", reply_markup=admin_main_kb())
            return
        for kid in expired:
            api_post('/api/admin/key/delete', {'key': kid})
        await update.message.reply_text(f"✅ Deleted {len(expired)} expired keys!", reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())

async def deact_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        keys = api_get('/api/admin/keys')
        active = [k for k,v in keys.items() if v.get('active') and k != ADMIN_TOKEN]
        for kid in active:
            api_post('/api/admin/key/update', {'key':kid,'active':False})
        await update.message.reply_text(f"✅ Deactivated {len(active)} keys!", reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())

# ═══════════════════════════════════════════════════════════════
# ADMIN: RESELLER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

async def reseller_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show reseller management menu"""
    try:
        resellers = api_get('/api/admin/resellers')
        if not resellers:
            lines = ["👥 *RESELLER MANAGEMENT*\n\n📭 No resellers yet."]
        else:
            lines = [f"👥 *RESELLER MANAGEMENT* ({len(resellers)} total)\n"]
            for rid, rd in resellers.items():
                st = '🟢' if rd.get('active',True) else '🔴'
                lines.append(f"{st} `{rid}` — {rd.get('name','?')}")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Reseller",    callback_data="res_add"),
             InlineKeyboardButton("🗑️ Remove Reseller", callback_data="res_del")],
            [InlineKeyboardButton("📋 View All",        callback_data="res_list"),
             InlineKeyboardButton("🔄 Toggle Active",   callback_data="res_toggle")],
        ])
        await update.message.reply_text('\n'.join(lines), parse_mode='Markdown', reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())

async def res_add_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("➕ *ADD RESELLER*\n\nSend reseller ID (e.g. RES001, JOHN):", parse_mode='Markdown')
    return WAIT_RES_ID

async def recv_res_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rid = update.message.text.strip().upper()
    ctx.user_data['new_res_id'] = rid
    await update.message.reply_text(f"👤 Reseller ID: `{rid}`\n\nSend reseller *name* (or skip):", parse_mode='Markdown')
    return WAIT_RES_NAME

async def recv_res_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    ctx.user_data['new_res_name'] = ctx.user_data['new_res_id'] if txt.lower() in ['skip','/skip'] else txt
    await update.message.reply_text("📝 Send *Telegram ID* of reseller (so they can use /start):\n\nOr type skip to skip:", parse_mode='Markdown')
    return WAIT_RES_NOTE

async def recv_res_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    tg_id = '' if txt.lower() in ['skip','/skip'] else txt
    rid = ctx.user_data['new_res_id']
    name = ctx.user_data['new_res_name']
    try:
        r = api_post('/api/admin/reseller/add', {'reseller_id': rid, 'name': name, 'note': tg_id})
        if r.get('ok'):
            token = r['token']
            # Store tg_id in resellers file
            if tg_id.isdigit():
                resellers = api_get('/api/admin/resellers')
                if rid in resellers:
                    resellers[rid]['tg_id'] = tg_id
                    api_post('/api/admin/resellers/update', {'reseller_id': rid, 'tg_id': tg_id})
            await update.message.reply_text(
                f"✅ *RESELLER ADDED!*\n\n"
                f"🆔 ID: `{rid}`\n"
                f"👤 Name: {name}\n"
                f"🔑 Token: `{token}`\n"
                f"📱 TG ID: {tg_id or '—'}\n\n"
                f"Share token with reseller!\n"
                f"They can use /start to login.",
                parse_mode='Markdown', reply_markup=admin_main_kb()
            )
        else:
            await update.message.reply_text(f"❌ {r.get('msg','Error')}", reply_markup=admin_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=admin_main_kb())
    ctx.user_data.clear()
    return ConversationHandler.END

async def res_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    try:
        resellers = api_get('/api/admin/resellers')
        keys = api_get('/api/admin/keys')
        if not resellers:
            await q.edit_message_text("📭 No resellers found!")
            return
        lines = ["📋 *ALL RESELLERS*\n"]
        for rid, rd in resellers.items():
            st = '🟢' if rd.get('active',True) else '🔴'
            total = sum(1 for v in keys.values() if v.get('owner') == rid)
            lines.append(
                f"{st} `{rid}` — {rd.get('name','?')}\n"
                f"   🔑 Keys: {total} | 🔑 Token: `{rd.get('token','?')}`\n"
                f"   📅 {rd.get('created','?')}"
            )
        await q.edit_message_text('\n'.join(lines), parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="res_back")]]))
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")

async def res_del_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    try:
        resellers = api_get('/api/admin/resellers')
        if not resellers:
            await q.edit_message_text("📭 No resellers to delete!")
            return
        buttons = []
        for rid, rd in resellers.items():
            buttons.append([InlineKeyboardButton(f"🗑️ {rid} — {rd.get('name','?')}", callback_data=f"res_del_confirm_{rid}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="res_back")])
        await q.edit_message_text("🗑️ *Select reseller to delete:*", parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")

async def res_del_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rid = q.data.replace("res_del_confirm_", "")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes Delete", callback_data=f"res_del_do_{rid}"),
         InlineKeyboardButton("❌ Cancel", callback_data="res_back")]
    ])
    await q.edit_message_text(f"⚠️ Delete reseller `{rid}`?\n\n(Their keys will remain)", parse_mode='Markdown', reply_markup=kb)

async def res_del_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rid = q.data.replace("res_del_do_", "")
    api_post('/api/admin/reseller/delete', {'reseller_id': rid})
    await q.edit_message_text(f"✅ Reseller `{rid}` deleted!", parse_mode='Markdown')

async def res_toggle_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    try:
        resellers = api_get('/api/admin/resellers')
        if not resellers:
            await q.edit_message_text("📭 No resellers!")
            return
        buttons = []
        for rid, rd in resellers.items():
            st = '🟢' if rd.get('active',True) else '🔴'
            buttons.append([InlineKeyboardButton(f"{st} {rid} — {rd.get('name','?')}", callback_data=f"res_toggle_do_{rid}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="res_back")])
        await q.edit_message_text("🔄 *Toggle reseller active/inactive:*", parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")

async def res_toggle_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rid = q.data.replace("res_toggle_do_", "")
    r = api_post('/api/admin/reseller/toggle', {'reseller_id': rid})
    st = '🟢 ACTIVE' if r.get('active') else '🔴 INACTIVE'
    await q.edit_message_text(f"✅ Reseller `{rid}` is now {st}", parse_mode='Markdown')

async def res_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("👥 Reseller management — use keyboard buttons below.")

# ═══════════════════════════════════════════════════════════════
# RESELLER USER SECTION
# ═══════════════════════════════════════════════════════════════

def get_res_ctx(ctx):
    return ctx.user_data.get('res_id'), ctx.user_data.get('res_token')

async def res_my_devices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rid, token = get_res_ctx(ctx)
    if not rid:
        await update.message.reply_text("⛔ Login with /start first.")
        return
    try:
        keys = api_get('/api/reseller/my-keys', headers=res_headers(token))
        today = datetime.now().strftime('%Y-%m-%d')
        if not keys:
            await update.message.reply_text("📭 No devices added yet.\nUse ➕ Add Device to add one.", reply_markup=reseller_main_kb())
            return
        lines = [f"📱 *MY DEVICES* ({len(keys)} total)\n"]
        for k, kd in keys.items():
            st = get_status(kd)
            dev = kd.get('device','—')
            ex = kd.get('expiry','♾️')
            nm = kd.get('name','?')
            lines.append(f"{st} 👤 {nm}\n   🔑 `{k}`\n   📱 `{dev}`\n   ⏰ {ex}\n")
        await update.message.reply_text('\n'.join(lines), parse_mode='Markdown', reply_markup=reseller_main_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=reseller_main_kb())

async def res_add_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rid, token = get_res_ctx(ctx)
    if not rid:
        await update.message.reply_text("⛔ Login with /start first.")
        return
    ctx.user_data['flow'] = 'add_device'
    await update.message.reply_text(
        "➕ *ADD DEVICE*\n\n"
        "Send the *Device ID* of the user:\n"
        "(e.g. Poscus-abc123xyz)",
        parse_mode='Markdown',
        reply_markup=cancel_kb()
    )
    return WAIT_R_DEVICE_ID

async def recv_r_device_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == "❌ Cancel":
        await update.message.reply_text("❌ Cancelled.", reply_markup=reseller_main_kb())
        return ConversationHandler.END
    ctx.user_data['r_device_id'] = update.message.text.strip()
    await update.message.reply_text(
        f"📱 Device ID: `{ctx.user_data['r_device_id']}`\n\n"
        f"👤 Send *user name* (or skip):",
        parse_mode='Markdown'
    )
    return WAIT_R_DEVICE_NAME

async def recv_r_device_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    ctx.user_data['r_device_name'] = '' if txt.lower() in ['skip','/skip'] else txt
    # Auto generate key
    ctx.user_data['r_key'] = gen_key("RS")
    await update.message.reply_text(
        f"✅ Key will be: `{ctx.user_data['r_key']}`\n\n"
        f"⏰ *Select expiry:*",
        parse_mode='Markdown',
        reply_markup=expiry_inline_kb("rexp")
    )
    return WAIT_R_EXPIRY_CONFIRM

async def recv_r_expiry(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if not q.data.startswith("rexp_"): return WAIT_R_EXPIRY_CONFIRM
    label, date = parse_expiry_cb(q.data, "rexp")
    ctx.user_data['r_expiry'] = date
    ctx.user_data['r_expiry_label'] = label

    device_id = ctx.user_data['r_device_id']
    name = ctx.user_data.get('r_device_name', '') or device_id
    key = ctx.user_data['r_key']

    # Confirm message with inline Yes/No
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Create Key", callback_data="r_confirm_yes"),
         InlineKeyboardButton("❌ Cancel",     callback_data="r_confirm_no")]
    ])
    await q.edit_message_text(
        f"📋 *CONFIRM KEY CREATION*\n\n"
        f"📱 Device: `{device_id}`\n"
        f"👤 Name: {name}\n"
        f"🔑 Key: `{key}`\n"
        f"⏰ Expiry: {label}\n\n"
        f"Do you want to create this key?",
        parse_mode='Markdown',
        reply_markup=kb
    )
    return WAIT_R_EXPIRY_CONFIRM

async def recv_r_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    rid, token = get_res_ctx(ctx)

    if q.data == "r_confirm_no":
        await q.edit_message_text("❌ Cancelled.")
        ctx.user_data.pop('flow', None)
        return ConversationHandler.END

    device_id = ctx.user_data['r_device_id']
    name = ctx.user_data.get('r_device_name','') or device_id
    key = ctx.user_data['r_key']
    expiry = ctx.user_data.get('r_expiry','')
    expiry_label = ctx.user_data.get('r_expiry_label','♾️ Lifetime')

    try:
        r = api_post('/api/reseller/add-device', {
            'device_id': device_id,
            'key': key,
            'expiry': expiry,
            'name': name,
        }, headers=res_headers(token))
        if r.get('ok'):
            await q.edit_message_text(
                f"✅ *DEVICE ADDED!*\n\n"
                f"📱 Device: `{device_id}`\n"
                f"👤 Name: {name}\n"
                f"🔑 Key: `{key}`\n"
                f"⏰ Expiry: {expiry_label}\n\n"
                f"Give this key to user! 🎉",
                parse_mode='Markdown'
            )
        else:
            await q.edit_message_text(f"❌ {r.get('msg','Error')}")
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")
    ctx.user_data.clear()
    ctx.user_data['role'] = 'reseller'
    ctx.user_data['res_id'] = rid
    ctx.user_data['res_token'] = token
    return ConversationHandler.END

async def res_remove_device_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rid, token = get_res_ctx(ctx)
    if not rid:
        await update.message.reply_text("⛔ Login with /start first.")
        return
    try:
        keys = api_get('/api/reseller/my-keys', headers=res_headers(token))
        if not keys:
            await update.message.reply_text("📭 No devices to remove!", reply_markup=reseller_main_kb())
            return ConversationHandler.END
        buttons = []
        for k, kd in keys.items():
            nm = kd.get('name', k)
            dev = kd.get('device','?')[:15]
            buttons.append([InlineKeyboardButton(f"🗑️ {nm} | {dev}", callback_data=f"r_del_{k}")])
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="r_del_cancel")])
        await update.message.reply_text("🗑️ *Select device to remove:*", parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(buttons))
        return WAIT_R_DEL_KEY
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=reseller_main_kb())
        return ConversationHandler.END

async def recv_r_del_device(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    if q.data == "r_del_cancel":
        await q.edit_message_text("❌ Cancelled.")
        return ConversationHandler.END
    kid = q.data.replace("r_del_","")
    rid, token = get_res_ctx(ctx)
    try:
        r = api_post('/api/reseller/remove-device', {'key': kid}, headers=res_headers(token))
        if r.get('ok'):
            await q.edit_message_text(f"✅ Device/Key `{kid}` removed!", parse_mode='Markdown')
        else:
            await q.edit_message_text(f"❌ {r.get('msg','Error')}")
    except Exception as e:
        await q.edit_message_text(f"❌ Error: {e}")
    return ConversationHandler.END

async def res_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rid, token = get_res_ctx(ctx)
    if not rid:
        await update.message.reply_text("⛔ Login with /start first.")
        return
    try:
        info = api_get('/api/reseller/info', headers=res_headers(token))
        keys = api_get('/api/reseller/my-keys', headers=res_headers(token))
        today = datetime.now().strftime('%Y-%m-%d')
        expired = sum(1 for v in keys.values() if v.get('expiry') and v['expiry'] < today)
        locked = sum(1 for v in keys.values() if v.get('device','').strip())
        await update.message.reply_text(
            f"📊 *MY STATS*\n\n"
            f"🆔 ID: `{rid}`\n"
            f"👤 Name: {info.get('name','?')}\n"
            f"🔑 Total Keys: `{info.get('total_keys',0)}`\n"
            f"🟢 Active: `{info.get('active_keys',0)}`\n"
            f"🟠 Expired: `{expired}`\n"
            f"📱 Device Locked: `{locked}`",
            parse_mode='Markdown', reply_markup=reseller_main_kb()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=reseller_main_kb())

async def res_exit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("👋 Logged out.", reply_markup=ReplyKeyboardRemove())

# ─── CANCEL ──────────────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=admin_main_kb())
    return ConversationHandler.END

async def cancel_inline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("❌ Cancelled.")

# ─── TEXT ROUTER ─────────────────────────────────────────────
async def text_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    uid = update.effective_user.id
    role = ctx.user_data.get('role')

    # Admin commands via reply keyboard
    if is_admin(uid):
        if txt == "📊 Stats":          return await show_stats(update, ctx)
        if txt == "📋 All Keys":       return await show_all_keys(update, ctx)
        if txt == "🗑️ Del Expired":    return await del_expired(update, ctx)
        if txt == "❌ Deact All":      return await deact_all(update, ctx)
        if txt == "👥 Resellers":      return await reseller_menu(update, ctx)
        if txt == "➕ Add Key":        return await add_key_start(update, ctx)
        if txt == "🔍 Search Key":     return await search_start(update, ctx)
        if txt == "🗑️ Delete Key":     return await del_key_start(update, ctx)
        if txt == "📱 Reset Device":   return await reset_dev_start(update, ctx)
        if txt == "⚡ Bulk Generate":  return await bulk_start(update, ctx)

    # Reseller commands via reply keyboard
    if role == 'reseller':
        if txt == "📱 My Devices":     return await res_my_devices(update, ctx)
        if txt == "➕ Add Device":     return await res_add_device_start(update, ctx)
        if txt == "🗑️ Remove Device":  return await res_remove_device_start(update, ctx)
        if txt == "📊 My Stats":       return await res_stats(update, ctx)
        if txt == "🔙 Exit":           return await res_exit(update, ctx)

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, text_router),
        ],
        states={
            # Admin add key flow
            WAIT_KEY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_key),
                         CallbackQueryHandler(use_auto_key, pattern="^use_auto_key$"),
                         CallbackQueryHandler(type_custom_key, pattern="^type_custom_key$")],
            WAIT_NAME:  [MessageHandler(filters.TEXT, recv_name)],
            WAIT_EXPIRY:[CallbackQueryHandler(recv_expiry_btn, pattern="^exp_")],
            WAIT_NOTE:  [MessageHandler(filters.TEXT, recv_note)],
            # Admin other flows
            WAIT_DEL_KEY:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_del_key)],
            WAIT_RESET_KEY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_reset_key)],
            WAIT_SEARCH:     [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_search)],
            WAIT_BULK_PREFIX:[MessageHandler(filters.TEXT, recv_bulk_prefix)],
            WAIT_BULK_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_bulk_count)],
            WAIT_BULK_DAYS:  [CallbackQueryHandler(recv_bulk_days, pattern="^bexp_")],
            # Admin reseller flows
            WAIT_RES_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_res_id)],
            WAIT_RES_NAME: [MessageHandler(filters.TEXT, recv_res_name)],
            WAIT_RES_NOTE: [MessageHandler(filters.TEXT, recv_res_note)],
            # Reseller device flows
            WAIT_R_DEVICE_ID:      [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_r_device_id)],
            WAIT_R_DEVICE_NAME:    [MessageHandler(filters.TEXT, recv_r_device_name)],
            WAIT_R_EXPIRY_CONFIRM: [CallbackQueryHandler(recv_r_expiry, pattern="^rexp_"),
                                    CallbackQueryHandler(recv_r_confirm, pattern="^r_confirm_")],
            WAIT_R_DEL_KEY:        [CallbackQueryHandler(recv_r_del_device, pattern="^r_del_")],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('start', start),
        ],
        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)

    # Inline callbacks (outside conv)
    app.add_handler(CallbackQueryHandler(confirm_del,     pattern="^confirm_del_"))
    app.add_handler(CallbackQueryHandler(cancel_inline,   pattern="^cancel_inline$"))
    app.add_handler(CallbackQueryHandler(res_add_start,   pattern="^res_add$"))
    app.add_handler(CallbackQueryHandler(res_list,        pattern="^res_list$"))
    app.add_handler(CallbackQueryHandler(res_del_start,   pattern="^res_del$"))
    app.add_handler(CallbackQueryHandler(res_del_confirm, pattern="^res_del_confirm_"))
    app.add_handler(CallbackQueryHandler(res_del_do,      pattern="^res_del_do_"))
    app.add_handler(CallbackQueryHandler(res_toggle_start,pattern="^res_toggle$"))
    app.add_handler(CallbackQueryHandler(res_toggle_do,   pattern="^res_toggle_do_"))
    app.add_handler(CallbackQueryHandler(res_back,        pattern="^res_back$"))

    print(f"🤖 Poscus Bot started! URL: {RENDER_URL}")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
