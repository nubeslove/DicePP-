from typing import List, Tuple, Any

from core.bot import Bot
from core.data import DataManagerError
from core.command.const import *
from core.command import UserCommandBase , custom_user_command
from core.command import BotCommandBase, BotSendMsgCommand
from core.communication import MessageMetaData, PrivateMessagePort, GroupMessagePort
from .initiative_list import DC_INIT
from utils.string import match_substring

LOC_BR_NEW = "battleroll_new"
LOC_BR_ROUND = "battleroll_round"
LOC_BR_ROUND_MOD = "battleroll_round_mod"
LOC_BR_TURN_MOD = "battleroll_turn_mod"
LOC_BR_ROUND_SHOW = "battleroll_turn_show"
LOC_BR_ROUND_NEXT = "battleroll_round_next"
LOC_BR_NO_INIT = "battleroll_no_init"
LOC_BR_TURN_END = "battleroll_turn_end"
LOC_BR_ROUND_NEW = "battleroll_round_new"
LOC_BR_TURN_NEW = "battleroll_turn_new"
LOC_BR_ERROR_NOT_NUMBER = "battleroll_error_not_number"
LOC_BR_ERROR_TOO_SMALL = "battleroll_error_too_small"
LOC_BR_ERROR_TOO_BIG = "battleroll_error_too_big"
LOC_BR_ERROR_NOT_FOUND = "battleroll_error_not_found"
LOC_BR_ERROR_TOO_MUCH_FOUND = "battleroll_error_too_much_found"
LOC_BR_ERROR_NOT_YOUR_TURN = "battleroll_error_not_your_turn"

LOC_BR_BUFF_SELF = "battleroll_buff_self"
LOC_BR_BUFF_TARGET_SINGLE = "battleroll_buff_target_single"
LOC_BR_BUFF_TARGET_MULTI = "battleroll_buff_target_multi"
LOC_BR_BUFF_TIME_KEYWORD = "battleroll_buff_time_keyword"

# 使用之前取消注释掉下面一行
@custom_user_command(readable_name="战斗轮指令",
                     priority=-1,
                     group_only=True,
                     flag=DPP_COMMAND_FLAG_BATTLE)
class BattlerollCommand(UserCommandBase):

    def __init__(self, bot: Bot):
        super().__init__(bot)
        bot.loc_helper.register_loc_text(LOC_BR_NEW, "已创建新战斗轮。清除先攻表、BUFF表、当前回合", "创建战斗轮")
        bot.loc_helper.register_loc_text(LOC_BR_ROUND, "现在是第{round}轮第{turn}回合，{turn_name}的回合", "查询当前轮次与回合数")
        bot.loc_helper.register_loc_text(LOC_BR_ROUND_MOD, "现在变成第{round}轮了", "修改当前轮次")
        bot.loc_helper.register_loc_text(LOC_BR_TURN_MOD, "现在变成第{round}轮的第{turn}回合了", "修改当前回合")
        bot.loc_helper.register_loc_text(LOC_BR_ROUND_SHOW, "现在是{turn_name}的回合", "编辑后显示的当前轮次与回合数")
        bot.loc_helper.register_loc_text(LOC_BR_NO_INIT, "目前先攻列表为空，故不存在回合与轮次", "当没有先攻列表的情况下询问回合")
        bot.loc_helper.register_loc_text(LOC_BR_TURN_END, "{turn_name}的回合结束了", "玩家或DM宣言回合结束")
        bot.loc_helper.register_loc_text(LOC_BR_ROUND_NEW, "新的一轮，现在是第{round}轮", "玩家或DM开始新的回合")
        bot.loc_helper.register_loc_text(LOC_BR_TURN_NEW, "现在是{turn_name}的回合", "玩家或DM开始新的回合")
        bot.loc_helper.register_loc_text(LOC_BR_ERROR_NOT_NUMBER, "这不是数字。", "当玩家输入的回合不为正整数时的报错")
        bot.loc_helper.register_loc_text(LOC_BR_ERROR_TOO_SMALL, "这个数字太小了", "当玩家输入一个过小的值时的报错")
        bot.loc_helper.register_loc_text(LOC_BR_ERROR_TOO_BIG, "这个数字太大了", "当玩家输入一个过大的值时的报错")
        bot.loc_helper.register_loc_text(LOC_BR_ERROR_NOT_FOUND, "没有找到这个回合", "当因没有对应回合而找不到对应回合时的回复")
        bot.loc_helper.register_loc_text(LOC_BR_ERROR_TOO_MUCH_FOUND, "找到复数回合，请换一个关键词", "当因出现复数可能回合而找不到对应回合时的回复")
        bot.loc_helper.register_loc_text(LOC_BR_ERROR_NOT_YOUR_TURN, "现在不是你的回合。该指令无法使用", "当出现一个要求玩家自己回合才能使用的指令时提示的报错")

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc: bool = False
        mode: str = ""
        arg_str: str = ""
        for key in ["br","battleroll","战斗轮"]:
            if msg_str.startswith("."+key):
                mode = "battleroll"
                should_proc = True
                arg_str = msg_str[len(key)+1:].strip()
                break
        for key in ["轮次","round"]:
            if msg_str.startswith("."+key):
                mode = "round"
                should_proc = True
                arg_str = msg_str[len(key)+1:].strip()
                break
        for key in ["回合","turn"]:
            if msg_str.startswith("."+key):
                mode = "turn"
                should_proc = True
                arg_str = msg_str[len(key)+1:].strip()
                break
        for key in ["跳过","skip"]:
            if msg_str.startswith("."+key):
                mode = "skip"
                should_proc = True
                arg_str = msg_str[len(key)+1:].strip()
                break
        for key in ["结束","ed"]:
            if msg_str.startswith("."+key):
                mode = "end"
                should_proc = True
                arg_str = msg_str[len(key)+1:].strip()
                break
        return should_proc, (not should_proc), (mode,arg_str)

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        port = GroupMessagePort(meta.group_id) if meta.group_id else PrivateMessagePort(meta.user_id)
        # 解析语句
        feedback: str = ""
        mode: str = hint[0]
        arg_str: str = hint[1]
        if mode == "battleroll":
            # 清理先攻
            try:
                self.bot.data_manager.delete_data(DC_INIT, [meta.group_id])
                feedback += self.format_loc(LOC_BR_NEW)
            except DataManagerError:
                feedback += "出错！"
        elif mode == "turn" or mode == "round":
            try:
                init_data: dict = self.bot.data_manager.get_data(DC_INIT, [meta.group_id])
            except DataManagerError:
                feedback = self.format_loc(LOC_BR_NO_INIT)
                return [BotSendMsgCommand(self.bot.account, feedback, [port])]
            # init_data.entities = sorted(init_data.entities, key=lambda x: -x.init)
            target_round: int = init_data.round
            target_turn: int = init_data.turn
            # 若无额外数值则显示当前回合，若额外有个数值则修改回合
            if not arg_str:
                feedback += self.format_loc(LOC_BR_ROUND,round=str(target_round),turn=str(target_turn),turn_name=init_data.entities[target_turn-1].name)
                return [BotSendMsgCommand(self.bot.account, feedback, [port])]
            elif arg_str.startswith("+"): # 检查是否为直接增加当前回合/轮次数
                modify_var: int = 0
                if arg_str == "++" or arg_str == "+":
                    modify_var = 1
                elif arg_str[1:].isdigit():
                    modify_var = int(arg_str[1:])
                else:
                    feedback += self.format_loc(LOC_BR_ERROR_NOT_NUMBER)
                    return [BotSendMsgCommand(self.bot.account, feedback, [port])]
                if mode == "turn":
                    target_turn += modify_var
                else: # if mode == "round"
                    target_round += modify_var
            elif arg_str.startswith("-"): # 检查是否为直接减少当前回合/轮次数
                if arg_str == "--" or arg_str == "-":
                    modify_var = 1
                elif arg_str[1:].isdigit():
                    modify_var = int(arg_str[1:])
                else:
                    feedback += self.format_loc(LOC_BR_ERROR_NOT_NUMBER)
                    return [BotSendMsgCommand(self.bot.account, feedback, [port])]
                if mode == "turn":
                    target_turn -= modify_var
                else: # if mode == "round"
                    target_round -= modify_var
            elif arg_str.startswith("="): # 检查是否为等于号直接修改
                if arg_str[1:].isdigit():
                    if mode == "turn":
                        target_turn = int(arg_str[1:])
                    else: # if mode == "round"
                        target_round = int(arg_str[1:])
                    # 因为使用等于号，还得检查是否超出轮内回合数
                    if target_turn > init_data.turns_in_round:
                        feedback += self.format_loc(LOC_BR_ERROR_TOO_BIG)
                        return [BotSendMsgCommand(self.bot.account, feedback, [port])]
                    elif target_turn < 1:
                        feedback += self.format_loc(LOC_BR_ERROR_TOO_SMALL)
                        return [BotSendMsgCommand(self.bot.account, feedback, [port])]
                else:
                    feedback += self.format_loc(LOC_BR_ERROR_NOT_NUMBER)
                    return [BotSendMsgCommand(self.bot.account, feedback, [port])]
            elif arg_str.isdigit(): #检查是否为数值，是的话直接替换，同等号
                if mode == "turn":
                    target_turn = int(arg_str)
                else: # if mode == "round"
                    target_round = int(arg_str)
            else: # 如果前面都不是，那么猜测这是一次指定对象的（代码从隔壁抄的）
                name_list = [entity.name for entity in init_data.entities]
                match_num = sum([e_name == arg_str for e_name in name_list])  
                if match_num == 1:  # 正好有一个同名条目
                    for i, entity in enumerate(init_data.entities):
                        if entity.name == arg_str:
                            target_turn = i + 1
                            break
                elif match_num == 0:  # 没有同名条目, 进入模糊搜索
                    possible_res: List[str] = match_substring(arg_str, name_list)
                    if len(possible_res) == 0:  # 没有结果
                        feedback += self.format_loc(LOC_BR_ERROR_NOT_FOUND)
                        return [BotSendMsgCommand(self.bot.account, feedback, [port])]
                    elif len(possible_res) > 1:  # 多个可能的结果
                        feedback += self.format_loc(LOC_BR_ERROR_TOO_MUCH_FOUND)
                        return [BotSendMsgCommand(self.bot.account, feedback, [port])]
                    elif len(possible_res) == 1:
                        for i, entity in enumerate(init_data.entities):
                            if entity.name == possible_res[0]:
                                target_turn = i + 1
                                break
                else: #if match_num > 1:  # 多于一个同名条目
                    feedback += self.format_loc(LOC_BR_ERROR_TOO_MUCH_FOUND)
                    return [BotSendMsgCommand(self.bot.account, feedback, [port])]
            # 经过修改后，检查是否回合超出轮内回合数
            if target_turn > init_data.turns_in_round:
                target_turn -= 1
                target_round += target_turn // init_data.turns_in_round
                target_turn = (target_turn % init_data.turns_in_round) + 1
            elif target_turn < 1:
                target_turn -= 1
                target_round -= (-target_turn) // init_data.turns_in_round
                target_turn = init_data.turns_in_round - (-target_turn % init_data.turns_in_round) + 1
            # 修改回合数与轮次数，并修改数据
            if init_data.round != target_round:
                init_data.round = target_round
                if len(feedback) > 0:
                    feedback += "\n"
                feedback += self.format_loc(LOC_BR_ROUND_MOD,round=str(target_round))
            if init_data.turn != target_turn:
                init_data.turn = target_turn
                if len(feedback) > 0:
                    feedback += "\n"
                feedback += self.format_loc(LOC_BR_TURN_MOD,turn=str(target_turn))
            self.bot.data_manager.set_data(DC_INIT, [meta.group_id], init_data)
            # 更新玩家姓名
            if init_data.entities[target_turn-1].owner:  
                init_data.entities[target_turn-1].name = self.bot.get_nickname(init_data.entities[target_turn-1].owner, meta.group_id)
            if len(feedback) > 0:
                feedback += "\n"
            feedback += self.format_loc(LOC_BR_ROUND_SHOW,turn_name=init_data.entities[target_turn-1].name)
            feedback = feedback.strip()
        elif mode == "end":
            try:
                init_data: dict = self.bot.data_manager.get_data(DC_INIT, [meta.group_id])
            except DataManagerError:
                feedback = self.format_loc(LOC_BR_NO_INIT)
                return [BotSendMsgCommand(self.bot.account, feedback, [port])]
            # 不需要再过排序了，现在自动排序的
            # init_data.entities = sorted(init_data.entities, key=lambda x: -x.init)
            round: int = init_data.round
            turn: int = init_data.turn
            # 更新回合结束者的名字
            if init_data.entities[turn-1].owner:
                init_data.entities[turn-1].name = self.bot.get_nickname(init_data.entities[turn-1].owner, meta.group_id)
            feedback += self.format_loc(LOC_BR_TURN_END,round=str(round),turn=str(turn),turn_name=init_data.entities[turn-1].name) + "\n"
            turn += 1
            if turn > init_data.turns_in_round:
                turn -= init_data.turns_in_round
                round += 1
                feedback += self.format_loc(LOC_BR_ROUND_NEW,round=str(round),turn=str(turn),turn_name=init_data.entities[turn-1].name) + "\n"
            # 更新回合开始者的名字
            if init_data.entities[turn-1].owner:
                init_data.entities[turn-1].name = self.bot.get_nickname(init_data.entities[turn-1].owner, meta.group_id)
            feedback += self.format_loc(LOC_BR_TURN_NEW,round=str(round),turn=str(turn),turn_name=init_data.entities[turn-1].name)
            init_data.round = round
            init_data.turn = turn
            init_data.first_turn = False
            self.bot.data_manager.set_data(DC_INIT, [meta.group_id], init_data)

        return [BotSendMsgCommand(self.bot.account, feedback, [port])]

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword == "br" or keyword == "战斗轮":  # help后的接着的内容
            feedback: str = ".br 或 .战斗轮 开始新的战斗轮"\
                            "\n.init 或 .先攻 查阅当前先攻表"\
                            "\n.ri+<调整值>  投掷先攻"\
                            "\n.turn 或 .round 或 .轮次 或 .回合 查看当前轮次与回合"\
                            "\n.round<数值> 或 .轮次<数值> 设置轮次数值"\
                            "\n.turn<数值> 或 .轮次<数值> 设置当前进行到的回合"\
                            "\n.skip<数量> 或 .跳过<数值> 跳过数回合"\
                            "\n.ed 或 .结束 在自己回合中宣言回合结束"
            return feedback
        return ""

    def get_description(self) -> str:
        return ".xxx 指令描述"  # help指令中返回的内容
