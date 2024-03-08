import aiohttp
import asyncio

from typing import List, Tuple, Any
from nonebot.adapters.onebot.v11 import Bot, Event, Message, MessageSegment, GroupMessageEvent,PrivateMessageEvent
from core.bot import Bot
from core.command.const import *
from core.command import UserCommandBase, custom_user_command
from core.command import BotCommandBase, BotSendMsgCommand
from core.communication import MessageMetaData, PrivateMessagePort, GroupMessagePort
import re
import os

# 改编自插件nonebot_plugin_ygo

ygo_max = 10

@custom_user_command(readable_name="YGO查卡指令",
                     priority=DPP_COMMAND_PRIORITY_DEFAULT,
                     flag=DPP_COMMAND_FLAG_FUN | DPP_COMMAND_FLAG_DND)
class UtilsYGOCommand(UserCommandBase):
    def __init__(self, bot: Bot):
        super().__init__(bot)
        self.mybot = bot

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        for key in ["查卡","ygo","卡"]:
            if msg_str.startswith("."+key):
                should_proc: bool = msg_str.startswith(".")
                should_pass: bool = False
                msg_str = msg_str[len(key):].strip()
        return should_proc, should_pass, msg_str
    
    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        if meta.group_id:
            port = GroupMessagePort(meta.group_id)# 另一边PrivateMessagePort(meta.user_id)
            try:
                asyncio.get_running_loop()
                self.tick_task = asyncio.create_task(ygo_find_card(self.mybot,port,hint))
            except RuntimeError:  # 在Debug中
                pass

async def ygo_find_card(bot: Bot, group_id: Any,key: str):
    imgs = (await get_card(key))[:ygo_max]
    msg = None
    for img in imgs:
        msg += MessageSegment.image(img)
    await send_forward_msg_group(bot, group_id, "霓石精查卡器", msg if msg else ["没有这样的卡片..."])
    #elif isinstance(event,PrivateMessageEvent):
        #await bot.send(event=event,message = msg if msg else "没有这样的卡片...")

async def get_card(key: str):
    url = f"https://ygocdb.com/?search={key}"
    headers = {
        'user-agent': 'nonebot-plugin-ygo',
        'referer': 'https://ygocdb.com/',
    }
    imgs = []
    async with aiohttp.ClientSession() as session:
        c = await session.get(url=url, headers=headers)
        text = (await c.content.read()).decode()
        imgs = re.findall('<img data-original="(.*?)!half">', text)
    return imgs

# 合并消息
async def send_forward_msg_group(bot: Bot, group_id: Any,name: str,msgs: [],):
    def to_json(msg):
        return {"type": "node", "data": {"name": name, "uin": bot.self_id, "content": msg}}
    messages = [to_json(msg) for msg in msgs]
    await bot.call_api("send_group_forward_msg", group_id=group_id, messages=messages)