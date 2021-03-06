from django_tgbot.decorators import processor
from django_tgbot.state_manager import message_types, update_types, state_types
from django_tgbot.types import inlinekeyboardbutton
from django_tgbot.types.replykeyboardmarkup import ReplyKeyboardMarkup
from django_tgbot.types.inlinekeyboardmarkup import InlineKeyboardMarkup
from django_tgbot.types.keyboardbutton import KeyboardButton
from django_tgbot.types.inlinekeyboardbutton import InlineKeyboardButton
from django_tgbot.types.update import Update
from django_tgbot.exceptions import ProcessFailure
from django.conf import settings

from ..bot import state_manager
from ..models import TelegramState
from ..bot import TelegramBot
from ..bot import dv
from ..models import Report

from enum import Enum
import numpy as np
import json
import re


class MessageText(Enum):
    WEL = 'Hi {},  Welcome to the CBIC.\nIf you are sure you are registered in the bot, click the “Authenticate”.\nOtherwise, contact to admin.'
    SLG = 'You has been authorized by {} mobile number'  # Successful login
    REP = 'The {} field has been entered before! Please choose another field'  # Repetitive
    NFU = 'The field {} not found! Please chose a valid field'  # Not FoUnd
    UEX = 'An unexpected problem occurred! Try enter the fields from first again'
    CHP = 'Choose {}th parameter'
    CHT = 'Choose target'
    CTD = 'Click on download button for downloading the chart'
    INV = 'Invalid Choice'
    CNL = 'If you want to cancel the process, click on cancel button'
    PVC = 'Please Enter a valid choice'
    FSU = 'The field registered'
    CFT = 'Choose a filter'
    FAD = 'Filter {} added successfully ✔'
    CHS = 'Select one of following items\:'
    FDN = 'The filter paramaters already have been set. Click on Save to apply the filter and Cancel to forget this filter'
    IFP = 'The filter param is invalid ✖\nPlease enter a valid value 🙏'
    NFT = 'We are in {}\\.\nYou can touch _*finish*_ button to go to the next step'  # Report State
    AFT = 'We are in {}\\.\nNow select your intended filters 🔍'  # Apply Filter
    RVA = 'The Values received successfully\\! \nClick on _*Save*_ button to apply these to filter'


class ButtonText(Enum):
    PAY = 'Payment'
    PIE = 'Pie Chart'
    GRP = 'Multi Group Chart'
    BAR = 'Bar Chart'
    LIN = 'Linear Chart'
    AUT = 'Authentication'
    DRW = 'Download'
    FNS = 'ّFinish'
    ACP = 'Accept'
    CNL = 'Cancel'


RESULT_PER_PAGE = 5

# Commands
charts = {
    ButtonText.PIE.value: 2,
    ButtonText.GRP.value: 3,
    ButtonText.BAR.value: 2,
    ButtonText.LIN.value: 2
}

MEDIA_STATE = 'query_filter'

buttons_dynamic_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/data/buttons.json"))
keyboards_dynamic_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/data/keyboards.json"))
states_dynamic_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/data/states.json"))
queries_dynamic_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/data/queries.json"))
filters_dynamic_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/data/filters.json"))

# * remove the filter names that are not in the columns of dataset
invalid_filters = []
for f_name, data in filters_dynamic_data.items():
    if data['type'] == 'multiSelect' and not dv.is_valid_column(f_name):
        invalid_filters.append(f_name)
[filters_dynamic_data.pop(f_name) for f_name in invalid_filters]

# * remove queries that have no chart for drawing
invalid_queires = []
for q_name, data in queries_dynamic_data.items():
    if not data['charts']:
        invalid_queires.append(q_name)
[queries_dynamic_data.pop(q_name) for q_name in invalid_queires]


buttons_static_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/static_data/buttons.json"))
keyboards_static_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/static_data/keyboards.json"))
states_static_data = json.load(
    open(settings.BASE_DIR/"bi_reports_illustrate_bot/static_data/states.json"))

# merge dynamic and static data
buttons_data, keyboards_data, states_data, queries_data, filters_data = [
    {}, {}, {}, {}, {}]

buttons_data.update(buttons_static_data)
buttons_data.update(buttons_dynamic_data)

keyboards_data.update(keyboards_static_data)
keyboards_data.update(keyboards_dynamic_data)

states_data.update(states_static_data)
states_data.update(states_dynamic_data)

queries_data.update(queries_dynamic_data)
filters_data.update(filters_dynamic_data)


# def get_markdown_from()

def get_message_from_update(bot: TelegramBot, update: Update):
    msg = ''
    try:
        if update.is_callback_query():
            callback_query = update.get_callback_query()
            msg = callback_query.get_data()
            bot.answerCallbackQuery(
                callback_query_id=callback_query.get_id(), text="Received!")
        else:
            msg = update.get_message().get_text()

        if button_trans.get(msg, None):
            msg = button_trans[msg]
    except Exception as e:
        print(str(e))
    return msg


def message_trans(state: TelegramState, msg: str):
    vars = re.findall('\{.*?\}', msg)
    for var in vars:
        trim_var = var[1:-1]
        parts = trim_var.split('.')
        state_obj = state.get_memory()
        result = state_obj
        for part in parts:
            result = result.get(part, None)
            if result is None:
                return None
        msg = msg.replace(var, result)
    return msg


def set_vars_from_msg(state: TelegramState, var: str, res: str):
    is_list = False
    if var[0] == '+':
        is_list = True
        var = var[1:]
    trim_var = var[1:-1]
    parts = trim_var.split('.')

    if len(parts) == 2:
        state_obj = state.get_memory().get(parts[0], {})
        if is_list:
            state_obj[parts[1]].append(res)
        else:
            state_obj[parts[1]] = res
        state.update_memory({parts[0]: state_obj})
    elif len(parts) == 1:
        if is_list:
            res = state.get_memory().get(parts[0], []).append(res)
        state.update_memory({parts[0]: res})


def go_to_prev_state(bot, state: TelegramState, msg=None):
    state_obj = state.get_memory()
    if state_obj.get("states", None):
        state_obj["states"].pop(-1)
        state.set_memory(state_obj)
    if state.name == MEDIA_STATE:
        next_state_name = state_obj["states"][0]
    else:
        next_state_name = re.sub('(.*)_.*', r'\1', state.name)
    go_to_state(bot, state, next_state_name, msg)


def go_to_state(bot: TelegramBot, state: TelegramState, state_name: str, msg=None):
    chat_id = state.telegram_chat.telegram_id
    state_obj = state.get_memory()

    msg = msg if msg else states_data[state_name]['msgs'][0]
    msg = message_trans(state, msg)
    keyboards_of_state = get_keyboards_of_state(state_name)
    if keyboards_of_state:
        state.set_name(state_name)
        print(msg)
        # reply keyboard
        bot.sendMessage(
            chat_id, msg, reply_markup=keyboards_of_state[0], parse_mode="MarkdownV2")
        if len(keyboards_of_state) == 2:
            if state_name == 'auth_home_reportsList':
                update_reports_list_config(state, 'init')
                msg = get_reports_list(state)
                state_obj = state.get_memory()
                kb_name = state_obj["reportsKeyboardName"]
                keyboards_of_state[1] = keyboards[kb_name]
            else:
                msg = states_data[state_name]['msgs'][1]
                msg = message_trans(state, msg)

            sent_msg = bot.sendMessage(
                chat_id=chat_id, text=msg, reply_markup=keyboards_of_state[1], parse_mode="MarkdownV2", disable_web_page_preview=True)  # inline keyboard
            state_obj["last_inline_message_id"] = sent_msg.get_message_id()
            # state.set_memory(state_obj)
    else:
        go_to_prev_state(bot, state)
        return

    if state_obj.get('states', None):
        try:
            bot.deleteMessage(chat_id, state_obj["last_inline_message_id"])
        except:
            pass
        inline_keyboard = get_inline_keyboard_of_state(state_obj['states'][-1])
        if inline_keyboard:
            sent_msg = bot.sendMessage(
                chat_id, MessageText.CHS.value, reply_markup=inline_keyboard, parse_mode="MarkdownV2")
            state_obj["last_inline_message_id"] = sent_msg.get_message_id()

    # save new state to database
    state.set_memory(state_obj)


def get_keyboards_of_state(state_name: str):
    try:
        return [keyboards[kb_name] for kb_name in states_data[state_name]['keyboards']]
    except:
        return None


def get_inline_keyboard_of_state(state_name: str):
    return inline_keyboards.get(state_name, None)


def update_reports_list_config(state: TelegramState, msg='init'):
    state_obj = state.get_memory()

    if msg == 'init':
        state_obj.pop('reportsListConfig', None)

    # get current page
    cur_page = None
    reports_list_config = state_obj.get("reportsListConfig", None)
    if reports_list_config:
        cur_page = reports_list_config.get("page", None)

    if not cur_page:
        cur_page = 1
    else:
        if msg == 'prev' and cur_page > 1:
            cur_page -= 1
        if msg == 'next' and cur_page + 1 <= reports_list_config["max_page"]:
            cur_page += 1

    total = Report.objects.filter(owner=state.telegram_user).count()
    report_pages = total / RESULT_PER_PAGE
    import math
    report_pages = math.ceil(report_pages)
    state_obj["reportsListConfig"] = {
        "page": cur_page, "per_page": RESULT_PER_PAGE, "max_page": report_pages, "total": total}

    kb_name = states_data[state.name]['keyboards'][1]
    if cur_page >= report_pages:
        kb_name += 'NoNext'
    if cur_page == 1:
        kb_name += 'NoPrev'
    state_obj["reportsKeyboardName"] = kb_name

    state.set_memory(state_obj)


def get_reports_list(state: TelegramState):
    reports_list_config = state.get_memory()["reportsListConfig"]
    cur_page = reports_list_config["page"]
    per_page = reports_list_config["per_page"]

    start_index = (cur_page - 1) * per_page
    end_index = start_index + per_page
    results = ""
    for ind, report in enumerate(Report.objects.filter(owner=state.telegram_user).order_by('-id')[start_index:end_index]):
        results += f"`{start_index + ind + 1}.`\n{report.get_with_icon()}\n"
    results += f"`Page {cur_page} of {reports_list_config['max_page']}, total {reports_list_config['total']}`"
    return results


def validate_filter_param(param: str):
    return True


def update_filter_message(bot: TelegramBot, state: TelegramState):
    pass


def get_filters_repr(filters: dict):
    res = ""
    for name, config in filters.items():
        if "choices" in config:
            config_repr = get_multi_select_repr(config)
        else:
            config_repr = get_min_max_repr(config)
        res += f"{name}:\n{config_repr}\n\n"
    return res


def get_multi_select_repr(filter_config: dict):
    return ', '.join(filter_config['choices'])


def get_min_max_repr(filter_config: dict):
    return f"from {filter_config['min']} to {filter_config['max']}"


# buttons translator
button_trans = {v['text']: k for k, v in buttons_data.items()}

# create keyboards
keyboards = dict()
for kb_name, data in keyboards_data.items():
    if data['type'] == 'inline':
        keyboards[kb_name] = InlineKeyboardMarkup.a(
            [[InlineKeyboardButton.a(
                text=buttons_data[btn]['text'], callback_data=buttons_data[btn]['text']) for btn in btn_list] for btn_list in data["buttons"]]
        )
    elif data['type'] == 'reply':
        keyboards[kb_name] = ReplyKeyboardMarkup.a(
            [[KeyboardButton.a(
                text=buttons_data[btn]['text']) for btn in btn_list] for btn_list in data["buttons"]],
            resize_keyboard=True
        )

# Keyboards
auth_keyboard = ReplyKeyboardMarkup.a(keyboard=[
    [
        KeyboardButton.a(
            text=buttons_data['auth']['text'], request_contact=True),
    ]
], resize_keyboard=True)

# create inline query keyboards
inline_keyboards = dict()

# create keyboard for queries of a leaf state
for st_name, data in states_data.items():
    queries = data.get('queries', None)
    if queries:
        query_keyboard_inline_buttons = list()
        for query_name in queries:
            query_keyboard_inline_buttons.append([
                InlineKeyboardButton.a(text=queries_data[query_name]['text'],
                                       callback_data=query_name
                                       )
            ])
        inline_keyboards[st_name] = InlineKeyboardMarkup.a(
            query_keyboard_inline_buttons)


for q_name, data in queries_data.items():
    # create keyboard for filters of a query
    filter_keyboard_inline_buttons = list()
    for filt in data['filters']:
        if filt in filters_data:
            filter_keyboard_inline_buttons.append([
                InlineKeyboardButton.a(text=filters_data[filt]["text"],
                                       callback_data=filt
                                       )
            ])
    if filter_keyboard_inline_buttons:
        inline_keyboards["query_filter_" +
                         q_name] = InlineKeyboardMarkup.a(filter_keyboard_inline_buttons)

    # create keyboard for charts of a query
    chart_keyboard_inline_buttons = list()
    for chart in data['charts']:
        chart_keyboard_inline_buttons.append([
            InlineKeyboardButton.a(text=chart,
                                   callback_data=chart
                                   )
        ])
    inline_keyboards["query_filter_run_" +
                     q_name] = InlineKeyboardMarkup.a(chart_keyboard_inline_buttons)


# add keyboard of each filter to inline keyboards
for f_name, data in filters_data.items():
    if data["type"] == 'multiSelect':
        adj_filter_keyboard_inline_buttons = list()
        for choice in dv.get_column_choices(f_name):
            adj_filter_keyboard_inline_buttons.append([
                InlineKeyboardButton.a(text=choice,
                                       callback_data=choice
                                       )
            ])
        inline_keyboards["query_filter_adjust_" +
                         f_name] = InlineKeyboardMarkup.a(adj_filter_keyboard_inline_buttons)
