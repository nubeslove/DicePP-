from typing import List, Tuple, Any

from core.bot import Bot
from core.command.const import *
from core.command import UserCommandBase, custom_user_command
from core.command import BotCommandBase, BotSendMsgCommand
from core.communication import MessageMetaData, GroupMessagePort, PrivateMessagePort
from module.common import DC_GROUPCONFIG
from module.roll.roll_config import DICE_TYPE_DEFAULT, DICE_TYPE_MAX

LOC_DSET_SUCCESS = "roll_default_dice_set_success"
LOC_DSET_INVALID = "roll_default_dice_set_invalid"
LOC_DSET_CURRENT = "roll_default_dice_current"

MIN_DICE_TYPE = 2


@custom_user_command(readable_name="默认骰设置指令",
                     priority=-1,
                     group_only=True,
                     flag=DPP_COMMAND_FLAG_MANAGE,
                     permission_require=1)
class DiceSetCommand(UserCommandBase):
    """.dset 设置群默认骰面"""

    def __init__(self, bot: Bot):
        super().__init__(bot)
        bot.loc_helper.register_loc_text(LOC_DSET_SUCCESS,
                                         "本群的默认掷骰面数已改为{dice}面。",
                                         "设置群默认骰面成功时的提示")
        bot.loc_helper.register_loc_text(LOC_DSET_INVALID,
                                         "骰面必须是介于{min_face}到{max_face}之间的整数。",
                                         "设置群默认骰面失败时的提示")
        bot.loc_helper.register_loc_text(LOC_DSET_CURRENT,
                                         "当前默认掷骰面数为{dice}面。使用 .dset [骰面] 进行修改。",
                                         "查询群默认骰面或缺少参数时的提示")

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc = msg_str.startswith(".dset")
        should_pass = False
        if not should_proc:
            return False, False, None
        arg = msg_str[5:].strip()
        return True, should_pass, arg

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
        arg: str = hint if hint is not None else ""
        if not arg:
            current = self.bot.data_manager.get_data(
                DC_GROUPCONFIG, [meta.group_id, "default_dice"], default_val=DICE_TYPE_DEFAULT
            )
            feedback = self.bot.loc_helper.format_loc_text(LOC_DSET_CURRENT, dice=current)
            return [BotSendMsgCommand(self.bot.account, feedback, [port])]

        cleaned_arg = arg
        if cleaned_arg.startswith("d"):
            cleaned_arg = cleaned_arg[1:]
        if cleaned_arg.endswith("d"):
            cleaned_arg = cleaned_arg[:-1]
        cleaned_arg = cleaned_arg.strip()
        if not cleaned_arg.isdigit():
            feedback = self.bot.loc_helper.format_loc_text(
                LOC_DSET_INVALID, min_face=MIN_DICE_TYPE, max_face=DICE_TYPE_MAX
            )
            return [BotSendMsgCommand(self.bot.account, feedback, [port])]

        dice_face = int(cleaned_arg)
        if dice_face < MIN_DICE_TYPE or dice_face > DICE_TYPE_MAX:
            feedback = self.bot.loc_helper.format_loc_text(
                LOC_DSET_INVALID, min_face=MIN_DICE_TYPE, max_face=DICE_TYPE_MAX
            )
            return [BotSendMsgCommand(self.bot.account, feedback, [port])]

        self.bot.data_manager.set_data(DC_GROUPCONFIG, [meta.group_id, "default_dice"], dice_face)
        feedback = self.bot.loc_helper.format_loc_text(LOC_DSET_SUCCESS, dice=dice_face)
        return [BotSendMsgCommand(self.bot.account, feedback, [port])]

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword == "dset":
            return ".dset [骰面]\n设置当前群的默认掷骰骰面"
        return ""

    def get_description(self) -> str:
        return ".dset [骰面] 设置群默认骰面"
