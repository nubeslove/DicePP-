import os
import datetime
from typing import List, Tuple, Any, Dict, Optional

from core.bot import Bot
from core.data import custom_data_chunk, DataChunkBase, DataManagerError
from core.command.const import *
from core.command import UserCommandBase, custom_user_command
from core.command import BotCommandBase, BotSendMsgCommand, BotSendFileCommand
from core.communication import MessageMetaData, GroupMessagePort
from utils.time import get_current_date_str, get_current_date_raw, datetime_to_str
from utils.logger import dice_log

# DataChunk 标识 / 存储结构
DC_LOG_SESSION = "log_session"
DCK_ACTIVE = "active"          # 是否正在记录
DCK_START_TIME = "start_time"  # 记录开始时间 (str)
DCK_RECORDS = "records"        # 记录的消息列表 List[Dict]
DCK_COLOR_MAP = "color_map"    # 用户ID -> 颜色 hex
DCK_FILTER_OUTSIDE = "filter_outside"  # 括号场外过滤
DCK_FILTER_COMMAND = "filter_command"  # 指令过滤
DCK_FILTER_BOT = "filter_bot"          # 骰娘自身过滤


@custom_data_chunk(identifier=DC_LOG_SESSION)
class _(DataChunkBase):  # noqa: E742 (单字符类名与其他 DataChunk 保持一致写法)
    def __init__(self):
        super().__init__()


COLOR_POOL = [
    "FF0000", "1E90FF", "228B22", "FF8C00", "9400D3", "DC143C", "20B2AA", "8B4513",
    "FF1493", "2E8B57", "4169E1", "DAA520", "C71585", "008B8B", "B03060", "556B2F",
]


def _pick_color(color_map: Dict[str, str], user_id: str) -> str:
    if user_id not in color_map:
        color_map[user_id] = COLOR_POOL[len(color_map) % len(COLOR_POOL)]
    return color_map[user_id]


def append_log_record(bot: Bot, group_id: str, user_id: str, nickname: str, content: str):
    """对外工具：向当前活动日志追加一条记录（若未开启则静默）。"""
    try:
        active = bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_ACTIVE], False)
        if not active:
            return
        try:
            records: List[Dict] = bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_RECORDS])
        except DataManagerError:
            records = []
            bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_RECORDS], records)
        color_map: Dict[str, str] = bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_COLOR_MAP], {})
        _pick_color(color_map, user_id)
        bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_COLOR_MAP], color_map)
        # 昵称兜底（Bot可能没有被update_nickname写入）
        if not nickname or nickname == "UNDEF_NAME":
            nickname = "骰娘"
        # 过滤（bot 写入也可能被用户要求过滤掉）
        if not should_filter_record(bot, group_id, user_id, content, is_bot=True):
            records.append({
                "time": get_current_date_str(),
                "user_id": user_id,
                "nickname": nickname or user_id,
                "content": content,
            })
            bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_RECORDS], records)
    except Exception:
        # 不让日志记录的异常影响主流程
        pass


def should_filter_record(bot: Bot, group_id: str, user_id: str, content: str, is_bot: bool = False) -> bool:
    """根据当前群的过滤配置判断是否过滤此消息。
    过滤规则：
    - outside: 消息整体被括号包裹 (支持全角/半角 ()（）) 时过滤
    - command: 以 '.' 或 '。' 开头的指令过滤
    - bot: 机器人自身消息过滤 (is_bot=True 时)
    """
    try:
        outside_f = bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_FILTER_OUTSIDE], False)
        command_f = bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_FILTER_COMMAND], False)
        bot_f = bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_FILTER_BOT], False)
    except Exception:
        return False

    text = content.strip()
    # outside: 判断是否用任意一对括号包裹
    if outside_f:
        if ( (text.startswith('(') and text.endswith(')')) or
             (text.startswith('（') and text.endswith('）')) ):
            return True
    if command_f:
        if text.startswith('.') or text.startswith('。'):
            return True
    if bot_f and is_bot:
        return True
    return False


LOC_LOG_ON_START = "log_on_start"            # 开始记录时
LOC_LOG_ON_ALREADY = "log_on_already"        # 已在记录
LOC_LOG_OFF_NOT_ACTIVE = "log_off_not_active"  # 关闭但未开启
LOC_LOG_OFF_RESULT = "log_off_result"        # 关闭并生成，{count}
LOC_LOG_USAGE = "log_usage"                  # 用法说明
LOC_LOG_SET_MENU = "log_set_menu"            # 设置菜单
LOC_LOG_SET_TOGGLED = "log_set_toggled"      # 切换结果
LOC_LOG_HELP = "log_help"                    # 完整帮助
LOC_LOG_FOLDER_FAIL = "log_folder_fail"      # 创建群文件夹失败
LOC_LOG_FOLDER_HINT = "log_folder_hint"      # 创建群文件夹提示
LOC_LOG_FOLDER_POLICY = "log_folder_policy"  # 启动时提示上传策略


@custom_user_command(readable_name="跑团日志指令", priority=DPP_COMMAND_PRIORITY_DEFAULT,
                     flag=DPP_COMMAND_FLAG_DEFAULT, cluster=DPP_COMMAND_CLUSTER_DEFAULT, group_only=True)
class LogCommand(UserCommandBase):
    """
    .log on  开始记录本群消息
    .log off 停止并生成日志文件
    """

    def __init__(self, bot: Bot):
        super().__init__(bot)
        # 注册本地化文本（会写入 localization.xlsx，可供自定义）
        bot.loc_helper.register_loc_text(LOC_LOG_ON_START, "新的故事开始了，祝旅途愉快！\n记录已经开启。", ".log on 开始记录时发送")
        bot.loc_helper.register_loc_text(LOC_LOG_ON_ALREADY, "日志记录已在进行中。", ".log on 但已经在记录时发送")
        bot.loc_helper.register_loc_text(LOC_LOG_OFF_NOT_ACTIVE, "当前没有进行中的日志记录。使用 .log on 开始。", ".log off 但尚未开启时发送")
        bot.loc_helper.register_loc_text(LOC_LOG_OFF_RESULT, "日志已生成，共 {count} 条消息。", ".log off 正常结束时发送，{count}=条目数")
        bot.loc_helper.register_loc_text(LOC_LOG_USAGE, "用法: .log on 开始记录；.log off 结束并生成。", ".log 指令使用帮助")
        bot.loc_helper.register_loc_text(LOC_LOG_SET_MENU,
                                         "日志过滤设置:\n"
                                         "1： outside / 场外发言过滤 启用状态： {outside} \n"
                                         "2： command / 指令过滤     启用状态： {command} \n"
                                         "3： bot / bot过滤          启用状态： {bot} \n"
                                         "切换示例: .log set outside  或  .log set 指令过滤\n"
                                         "仅输入 .log set 显示本菜单。",
                                         ".log set 菜单")
        bot.loc_helper.register_loc_text(LOC_LOG_SET_TOGGLED, "已切换 {item} -> {state}", ".log set 某项被切换时反馈")
        bot.loc_helper.register_loc_text(LOC_LOG_HELP,
                                         "日志功能指令: \n"
                                         ".log on  开始记录\n"
                                         ".log off 结束记录并生成文件(docx+txt)\n"
                                         ".log set  查看/切换过滤开关 (支持: outside/场外发言过滤, command/指令过滤, bot/bot过滤)\n"
                                         ".log set <选项> 切换对应过滤。\n"
                                         "过滤说明: \n场外发言过滤=过滤括号内信息\n指令过滤=过滤以句号起始指令\nbot过滤=过滤骰娘自身消息。",
                                         ".log 完整帮助")
        bot.loc_helper.register_loc_text(LOC_LOG_FOLDER_FAIL, "权限不足，无法创建跑团log文件夹，已上传至根目录。", "创建群文件夹失败")
        bot.loc_helper.register_loc_text(LOC_LOG_FOLDER_HINT, "日志文件将上传到群文件夹: 跑团log", "创建群文件夹提示")
        bot.loc_helper.register_loc_text(LOC_LOG_FOLDER_POLICY,
                                         "说明：若群文件存在‘跑团log’文件夹，日志文件将上传到该文件夹；若不存在则上传至群文件根目录。",
                                         ".log on 时提示日志文件夹策略")

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        should_proc = msg_str.startswith(".log")
        if not should_proc:
            return False, False, None
        args = msg_str.split()
        action = args[1].lower() if len(args) > 1 else ""
        param = args[2].lower() if len(args) > 2 else ""
        return True, False, (action, param)  # 不继续传递

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        action, param = hint if isinstance(hint, tuple) else (hint, "")
        group_id = meta.group_id
        if not group_id:
            return []

        feedback = ""
        active = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_ACTIVE], False)
        if action == "on":
            if active:
                feedback = self.format_loc(LOC_LOG_ON_ALREADY)
            else:
                start_time = get_current_date_str()
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_ACTIVE], True)
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_START_TIME], start_time)
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_RECORDS], [])
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_COLOR_MAP], {})
                # 初始化过滤配置（保留所有信息）
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_FILTER_OUTSIDE], False)
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_FILTER_COMMAND], False)
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_FILTER_BOT], False)
                feedback = self.format_loc(LOC_LOG_ON_START) + "\n" + self.format_loc(LOC_LOG_FOLDER_POLICY)
        elif action == "off":
            if not active:
                feedback = self.format_loc(LOC_LOG_OFF_NOT_ACTIVE)
            else:
                # 结束 & 生成文件
                records = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_RECORDS], [])
                start_time = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_START_TIME], "unknown_start")
                color_map = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_COLOR_MAP], {})
                self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_ACTIVE], False)
                file_main_path, display_name, extra_files = self._generate_file(group_id, start_time, records, color_map)
                feedback = self.format_loc(LOC_LOG_OFF_RESULT, count=len(records))
                port = GroupMessagePort(group_id)
                folder_prefix = "跑团log/"  # 仅当群里已存在该文件夹时适配器会放进去；否则上传到根目录
                cmds: List[BotCommandBase] = [BotSendMsgCommand(self.bot.account, feedback, [port]),
                                              BotSendFileCommand(self.bot.account, file_main_path, folder_prefix + display_name, [port])]
                for fpath, fname in extra_files:
                    cmds.append(BotSendFileCommand(self.bot.account, fpath, folder_prefix + fname, [port]))
                return cmds
        elif action == "set":
            # 允许未开启时预配置
            for base_key in (DCK_RECORDS, DCK_COLOR_MAP):
                try:
                    _ = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, base_key])
                except DataManagerError:
                    self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, base_key], [] if base_key == DCK_RECORDS else {})
            for flag in (DCK_FILTER_OUTSIDE, DCK_FILTER_COMMAND, DCK_FILTER_BOT):
                try:
                    _ = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, flag])
                except DataManagerError:
                    self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, flag], False)
            if not param:
                outside = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_FILTER_OUTSIDE], False)
                command_f = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_FILTER_COMMAND], False)
                bot_f = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_FILTER_BOT], False)
                feedback = self.format_loc(LOC_LOG_SET_MENU,
                                           outside="ON" if outside else "OFF",
                                           command="ON" if command_f else "OFF",
                                           bot="ON" if bot_f else "OFF") + (" (记录未开启)" if not active else "")
            else:
                key_map = {
                    "outside": DCK_FILTER_OUTSIDE,
                    "场外发言过滤": DCK_FILTER_OUTSIDE,
                    "command": DCK_FILTER_COMMAND,
                    "指令过滤": DCK_FILTER_COMMAND,
                    "bot": DCK_FILTER_BOT,
                    "bot过滤": DCK_FILTER_BOT,
                }
                if param in key_map:
                    cur = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, key_map[param]], False)
                    self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, key_map[param]], not cur)
                    feedback = self.format_loc(LOC_LOG_SET_TOGGLED, item=param, state="ON" if (not cur) else "OFF") + (" (记录未开启，已保存)") if not active else ""
                else:
                    feedback = "未知选项，可用: outside/场外发言过滤 | command/指令过滤 | bot/bot过滤"
        elif action == "":
            # 仅 .log -> 完整帮助
            feedback = self.format_loc(LOC_LOG_HELP)
        else:
            feedback = self.format_loc(LOC_LOG_USAGE)

        return [BotSendMsgCommand(self.bot.account, feedback, [GroupMessagePort(group_id)])]

    def _generate_file(self, group_id: str, start_time: str, records: List[Dict], color_map: Dict[str, str]) -> Tuple[str, str, List[Tuple[str,str]]]:
        """生成 docx 和 txt 文件；并对连续同一用户的消息合并显示(横线分隔)。
        返回: (主文件路径, 主文件名, 额外文件列表[(path,name),...])"""
        logs_dir = os.path.join(self.bot.data_path, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        safe_start = start_time.replace(":", "-").replace(" ", "_")
        display_name_base = f"log_{group_id}_{safe_start}"
        # 合并逻辑：遍历记录，若连续同一user则只写一次头，其余用 ---- + time 分隔
        def iter_grouped(recs: List[Dict]):
            last_uid = None
            first_of_block = True
            for rec in recs:
                uid = rec['user_id']
                if uid != last_uid:
                    first_of_block = True
                    last_uid = uid
                yield rec, first_of_block
                first_of_block = False

        txt_path = os.path.join(logs_dir, display_name_base + ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"群 {group_id} 跑团日志 (开始于 {start_time})\n\n")
            for rec, first in iter_grouped(records):
                # 兜底修正机器人昵称缺失或异常占位
                if rec.get('user_id') == self.bot.account and (not rec.get('nickname') or rec.get('nickname') in ("UNDEF_NAME", "----")):
                    rec['nickname'] = "骰娘"
                if first:
                    f.write(f"{rec['nickname']} ({rec['user_id']})  {rec['time']}\n")
                    f.write(rec['content'] + "\n")
                else:
                    f.write(f"---- {rec['time']}\n")
                    f.write(rec['content'] + "\n")
                f.write("\n")

        docx_path = None
        try:
            from docx import Document  # type: ignore
            from docx.shared import RGBColor  # type: ignore
            doc = Document()
            doc.add_heading(f"群 {group_id} 跑团日志 (开始于 {start_time})", level=1)
            last_uid = None
            first_block = True
            for rec, first in iter_grouped(records):
                uid = rec['user_id']
                color_hex = color_map.get(uid, "000000")
                r = int(color_hex[0:2], 16); g = int(color_hex[2:4], 16); b = int(color_hex[4:6], 16)
                # 兜底修正机器人昵称
                if rec.get('user_id') == self.bot.account and (not rec.get('nickname') or rec.get('nickname') in ("UNDEF_NAME", "----")):
                    rec['nickname'] = "骰娘"
                if first:  # 头部
                    header = doc.add_paragraph()
                    run1 = header.add_run(f"{rec['nickname']} ({uid})  {rec['time']}")
                    run1.font.color.rgb = RGBColor(r, g, b)
                    body_p = doc.add_paragraph()
                    run2 = body_p.add_run(rec['content'])
                    run2.font.color.rgb = RGBColor(r, g, b)
                else:
                    sep_p = doc.add_paragraph()
                    sep_run = sep_p.add_run(f"---- {rec['time']}")
                    sep_run.font.color.rgb = RGBColor(r, g, b)
                    body_p = doc.add_paragraph()
                    run2 = body_p.add_run(rec['content'])
                    run2.font.color.rgb = RGBColor(r, g, b)
            docx_path = os.path.join(logs_dir, display_name_base + ".docx")
            doc.save(docx_path)
        except Exception as e:
            # 记录失败原因，便于诊断（如服务器环境丢失依赖、权限问题等）
            try:
                dice_log(f"[LogExport] docx generation failed: {type(e).__name__}: {e}")
            except Exception:
                pass
            docx_path = None

        extra: List[Tuple[str,str]] = []
        if docx_path:
            # 主文件用docx，额外上传txt
            extra.append((txt_path, os.path.basename(txt_path)))
            return docx_path, os.path.basename(docx_path), extra
        else:
            return txt_path, os.path.basename(txt_path), []

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        if keyword in ("log", "日志"):
            return self.format_loc(LOC_LOG_USAGE)
        return ""

    def get_description(self) -> str:
        return ".log on/off 记录跑团日志"


@custom_user_command(readable_name="跑团日志记录器", priority=DPP_COMMAND_PRIORITY_DEFAULT - 50,
                     flag=0, cluster=DPP_COMMAND_CLUSTER_DEFAULT, group_only=True)
class LogRecorderCommand(UserCommandBase):
    """负责在开启状态下采集所有普通消息 (不以'.'开头)"""

    def __init__(self, bot: Bot):
        super().__init__(bot)

    def can_process_msg(self, msg_str: str, meta: MessageMetaData) -> Tuple[bool, bool, Any]:
        if not meta.group_id:
            return False, False, None
        is_active = self.bot.data_manager.get_data(DC_LOG_SESSION, [meta.group_id, DCK_ACTIVE], False)
        if not is_active:
            return False, False, None
        # 现在指令也记录；继续传递给后续命令
        return True, True, None

    def process_msg(self, msg_str: str, meta: MessageMetaData, hint: Any) -> List[BotCommandBase]:
        group_id = meta.group_id
        # 读取当前数据
        try:
            records: List[Dict] = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_RECORDS])
        except DataManagerError:
            records = []
            self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_RECORDS], records)
        color_map: Dict[str, str] = self.bot.data_manager.get_data(DC_LOG_SESSION, [group_id, DCK_COLOR_MAP], {})
        _pick_color(color_map, meta.user_id)
        self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_COLOR_MAP], color_map)

        # 内容策略：判断原始 raw 是否以半角 . 或全角 。 开头，原样记录；否则记录 raw（保留CQ码）
        raw = getattr(meta, 'raw_msg', '') or msg_str
        if raw.startswith('.') or raw.startswith('。'):
            content = raw  # 指令保持原样
        else:
            content = raw

        # 过滤逻辑
        if should_filter_record(self.bot, group_id, meta.user_id, content):
            return []
        records.append({
            "time": get_current_date_str(),
            "user_id": meta.user_id,
            "nickname": meta.nickname or meta.user_id,
            "content": content,
        })
        self.bot.data_manager.set_data(DC_LOG_SESSION, [group_id, DCK_RECORDS], records)
        return []  # 不产生机器人操作

    def get_help(self, keyword: str, meta: MessageMetaData) -> str:
        return ""

    def get_description(self) -> str:
        return ""  # 隐藏
