"""Read the counted managers and per-manager tactic sections of an FM27 career."""
from collections import ChainMap
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import date
import struct

from fmsave import _checks, _version
from fmsave._errors import CorruptSaveError, ReaderCheckError
from fmsave._layouts import SaveSummaryLayout, find_layout
from fmsave.models.managed import ManagedClub
from fmsave.readers import managed, tactics

HUMAN_RECORD_SEPARATOR = b'\xff\xff\x00\x01\xd8\x0e\xff\xff\xff\xff'
HUMAN_RECORD_HEADER = b'\x11\x00\x01'


@dataclass(frozen=True)
class CareerSummary:
    clock: tuple[date, int]
    managers: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class ManagerTactics:
    club: ManagedClub
    selector: int
    section: bytes


def read_career_summary(data, layout, build):
    offset = layout.structured_strings_offset
    read_string = _version.read_length_prefixed_string
    try:
        setup, offset = read_string(data, offset, layout.max_setup_string_bytes)
        stored_build, offset = read_string(data, offset, layout.max_version_bytes)
        divisions = _version.read_u32(data, offset)
        if stored_build != build or divisions > layout.max_divisions or not (setup or divisions):
            return None
        offset += 4
        for _ in range(divisions):
            _, offset = read_string(data, offset, layout.max_summary_name_bytes)
        offset += layout.manager_header_bytes
        if offset > len(data):
            return None
        count = data[offset - 1]
    except CorruptSaveError:
        return None
    if count < 2:
        return None

    managers = []
    try:
        for _ in range(count):
            name, offset = read_string(data, offset, layout.max_summary_name_bytes)
            club_name, offset = read_string(data, offset, layout.max_summary_name_bytes)
            club_id = _version.read_u32(data, offset)
            if not name or bool(club_name) != (club_id not in (0, 0xffffffff)):
                raise ReaderCheckError('FM27 多人执教存档的经理摘要字段不完整')
            managers.append((club_id, name))
            offset += layout.club_uid_bytes
        game_date = _version.decode_date(data, offset)
        if game_date is None:
            raise ReaderCheckError('FM27 多人执教存档的摘要日期无效')
        return CareerSummary((game_date, _version.decode_time_slot(data, offset)), tuple(managers))
    except CorruptSaveError as error:
        raise ReaderCheckError('FM27 多人执教存档的经理摘要提前结束') from error


def _tactic_sections(section, layout, file_name):
    starts = tactics._stored_block_starts(section, layout, file_name)
    if not starts or starts[0] != layout.first_block_offset:
        raise ReaderCheckError(f'{file_name}: 找不到多人执教战术表的第一个球队区块')
    prefix = section[:layout.header_marker_offset]
    header_length = layout.first_block_offset - len(prefix)
    group_headers = []
    at = 0
    while at < len(starts):
        header = starts[at] - header_length
        selector, count = tactics.read_tactics_header(
            prefix + section[header:starts[at]], layout, file_name
        )
        if not selector or not 1 <= count <= len(starts) - at:
            raise ReaderCheckError(f'{file_name}: 多人执教战术表的球队数量或经理引用无效')
        group_headers.append((selector, header))
        at += count
    if len({selector for selector, _ in group_headers}) != len(group_headers):
        raise ReaderCheckError(f'{file_name}: 多人执教战术表的经理区块重复')
    ends = [header for _, header in group_headers[1:]] + [len(section)]
    return {selector: prefix + section[start:end]
            for (selector, start), end in zip(group_headers, ends)}


def additional_selectors(humans):
    selectors = []
    start = humans.find(HUMAN_RECORD_SEPARATOR)
    while start >= 0:
        offset = start + len(HUMAN_RECORD_SEPARATOR)
        if humans.startswith(HUMAN_RECORD_HEADER, offset + 4):
            selectors.append(struct.unpack_from('<I', humans, offset)[0])
        start = humans.find(HUMAN_RECORD_SEPARATOR, offset)
    return selectors


def _read_manager_tactics(save):
    from desktop_save_compat import LATER_BUILDS

    info = save.info
    if info.build not in LATER_BUILDS or info.section_schemas.get('save_game_summary') != 31:
        return None
    context = save._context
    layout = find_layout(SaveSummaryLayout, 'save_game_summary', 31, info.build).layout
    with context.section('save_game_summary') as data:
        summary = read_career_summary(data, layout, info.build)
    if summary is None:
        return None
    layouts = managed.find_managed_club_layouts(info.section_schemas, info.build)
    with context.section('humans') as humans, context.section('tactics_man') as section:
        count, first = managed._first_human(humans, layouts.humans, info.file_name) or (0, 0)
        if count != len(summary.managers):
            raise ReaderCheckError(f'{info.file_name}: 存档摘要与人类经理表的计数不一致')
        tactic_layout = tactics.find_tactics_layout(info.section_schemas.get('tactics_man'), info.build)
        groups = _tactic_sections(section, tactic_layout, info.file_name)
        if next(iter(groups)) != first:
            raise ReaderCheckError(f'{info.file_name}: 多人执教战术表与首位经理引用不一致')
        # The later human records store this separator before their one-based person reference.
        selectors = additional_selectors(humans)
        if any(selectors.count(selector) != 1 for selector in tuple(groups)[1:]):
            raise ReaderCheckError(f'{info.file_name}: 战术表的经理引用未在人类经理表中唯一找到')

    by_club = {}
    with context.section('game_db') as game_db:
        index = context.club_index()
        for selector, section in groups.items():
            club = managed._chain_record_club(game_db, selector, index, info.game_date,
                                               layouts.contracts, info.file_name)
            if club is None:
                continue
            staff_uid = managed._manager_staff_uid(game_db, selector, layouts.humans, layouts.staff)
            if staff_uid is None or club.unique_id in by_club:
                raise ReaderCheckError(f'{info.file_name}: 无法唯一核对多人执教俱乐部与经理身份')
            by_club[club.unique_id] = (club, staff_uid, selector, section)
    summary_clubs = [(club_id, name) for club_id, name in summary.managers if club_id not in (0, 0xffffffff)]
    if len(summary_clubs) != len(by_club) or {club_id for club_id, _ in summary_clubs} != by_club.keys():
        raise ReaderCheckError(f'{info.file_name}: 存档摘要与经理合同的俱乐部 ID 不一致')
    return tuple(
        ManagerTactics(ManagedClub(club.uid, club.name, club.short_name, name, staff_uid, None, None, None),
                       selector, section)
        for club_id, name in summary_clubs
        for club, staff_uid, selector, section in (by_club[club_id],)
    )


def manager_tactics(save):
    return save._context.cached('desktop:multiplayer_career', lambda: _read_manager_tactics(save))


def managed_clubs(save):
    career = manager_tactics(save)
    return save.managed_clubs() if career is None else tuple(group.club for group in career)


def read_tactics(save, group, layout):
    context = save._context
    index = context.club_index()
    club_uid = group.club.club_uid
    team_ids = [team.team_id for team in index.club_by_uid[club_uid].teams]
    players = save.players()
    records = context.player_records()
    blocks, counts = tactics.walk_tactic_blocks(group.section, team_ids, layout, save.info.file_name)
    header_selector, _ = tactics.read_tactics_header(group.section, layout, save.info.file_name)
    rows, _, stats = tactics.build_tactic_tables(
        blocks, index, records, players, club_uid, header_selector, group.selector, counts
    )
    selections, selection_stats = tactics.build_selection_table(
        blocks, index, records, players, club_uid, layout.slot_count
    )
    bounds = save._gate_bounds()
    size = index.game_db_bytes
    save._enforce_checks((_checks.check_tactics(stats, bounds, size), _checks.check_set_pieces(stats, bounds, size)))
    return rows, selections, _checks.check_selections(selection_stats, bounds, size)


def install_staff_reader(human_layouts):
    from fmsave import _save
    from fmsave.readers import staff

    read_staff = _save.read_staff
    discover = staff.discover_contracts
    excluded_people = ContextVar('fm27_staff_additional_human_people', default=())

    def read(game_db, humans, clubs, players, names, clock, layouts, filename):
        selectors = ()
        if layouts.humans in human_layouts:
            header = managed._first_human(humans, layouts.humans, filename)
            if header and header[0] > 1:
                candidates = additional_selectors(humans)
                if len(candidates) == len(set(candidates)) == header[0] - 1 and header[1] not in candidates:
                    selectors = tuple(selector for selector in candidates if 0 < selector < 0xffffffff
                                      and staff.locate_human_header(game_db, selector, layouts.staff) is not None)
        token = excluded_people.set(selectors)
        try:
            return read_staff(game_db, humans, clubs, players, names, clock, layouts, filename)
        finally:
            excluded_people.reset(token)

    def discover_ai_contracts(game_db, players, first, decoder, layouts, clubs):
        if selectors := excluded_people.get():
            # Discovery already skips the player ownership index and the first human.
            # Extend its membership filter only for confirmed additional human objects.
            excluded = dict.fromkeys((selector - 1 for selector in selectors), -1)
            players = replace(players, position_by_pindex=ChainMap(excluded, players.position_by_pindex))
        return discover(game_db, players, first, decoder, layouts, clubs)

    _save.read_staff = read
    staff.discover_contracts = discover_ai_contracts
