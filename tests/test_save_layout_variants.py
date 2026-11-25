import io
import struct
import sys
import unittest
from contextlib import nullcontext
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import desktop_save_compat
from desktop_save_setpieces import routine_header_bytes
from desktop_save_multiplayer import read_career_summary
from fmsave import _container, _context
from fmsave._errors import CorruptSaveError
from fmsave._layouts import SaveSummaryLayout, find_layout
from fmsave.readers import tactics


class SaveLayoutVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        desktop_save_compat.install()
        cls.layout = tactics.find_tactics_layout(26, '27.0.1+2503222')

    def test_counted_career_summary_reads_clock_after_all_managers(self):
        build = '27.1.0+2505117'
        layout = find_layout(SaveSummaryLayout, 'save_game_summary', 31, build).layout

        def field(value):
            encoded = value.encode('utf8')
            return struct.pack('<I', len(encoded)) + encoded

        header = bytes(layout.structured_strings_offset) + field('setup') + field(build)
        header += struct.pack('<I', 1) + field('Division')
        header += bytes(layout.manager_header_bytes - 1) + b'\x03'
        rows = (
            field('Same Name') + field('Newcastle') + struct.pack('<I', 688)
            + field('Same Name') + field('Hertha') + struct.pack('<I', 2247)
            + field('Another Name') + field('Aberdeen') + struct.pack('<I', 1536)
        )
        packed_date = struct.pack('<HH', (25 << 9) | 210, 2026)
        result = read_career_summary(header + rows + packed_date, layout, build)
        self.assertEqual(result.clock, (date(2026, 7, 29), 25))
        self.assertEqual(result.managers, ((688, 'Same Name'), (2247, 'Same Name'), (1536, 'Another Name')))
        with self.assertRaises(tactics.ReaderCheckError):
            read_career_summary(header + rows[:-1], layout, build)
        self.assertIsNone(read_career_summary(header[:-1] + b'\x01' + rows, layout, build))

    def test_fm27_calendar_budget_does_not_count_unread_directory_entries(self):
        region = _context.SPAN_REGION
        frame = _container.zstd.compress(bytes(64))
        entry = _container.DirectoryEntry('unread', '.dat', 0, 1, 64, (0, 0))
        index = _container.ContainerIndex(Path('test.fm'), _container.Fingerprint(0, 0, ''),
                                          'test.fm', 0, (entry,), {}, {},
                                          _container.ContainerLimits(80, 80))
        info = SimpleNamespace(game='FM27', build='27.1.0+2505117',
                               game_date=date(2029, 2, 6), file_name=index.file_name)
        context = SimpleNamespace(info=info, _container_index=index)
        index.regions[region] = _container.Region(region, 0, len(frame), None)
        with patch.object(_container, 'open_verified', side_effect=lambda _: nullcontext(io.BytesIO(frame))):
            with self.assertRaisesRegex(CorruptSaveError, 'total decompression cap'):
                list(_container.read_region_frames(index, region))
            records = _context.SaveContext._build_span_records(context)
            self.assertEqual((records.span_bytes, records.frame_count), (64, 1))
        index.regions[region] = _container.Region(region, 0, len(frame) * 2, None)
        with (
            patch.object(_container, 'open_verified', side_effect=lambda _: nullcontext(io.BytesIO(frame * 2))),
            patch.object(_container, 'changed_since_index', return_value=False),
        ):
            with self.assertRaisesRegex(CorruptSaveError, 'more than 16 bytes'):
                _context.SaveContext._build_span_records(context)

    def selection(self, footer, following):
        layout = self.layout
        empty_lists = struct.pack('<I', 0)
        header = struct.pack('<I', 42) + layout.block_marker
        header += struct.pack('<I', 2) + b'XI'
        header += struct.pack('<I', 123) * layout.selection_slot_count
        header += layout.selection_end_marker + empty_lists * 2
        header += bytes([layout.list_item_lead_byte]) + struct.pack('<I', 123)
        header += layout.taker_markers[0] + empty_lists * layout.taker_list_count
        header += layout.order_marker + empty_lists * layout.order_list_count
        return header + footer + following

    def test_extended_selection_requires_tactic_at_declared_boundary(self):
        footer = bytes.fromhex('01 05 01 00 00 00 00 01 00')
        signature = self.layout.alternate_signature
        data = self.selection(footer, signature)
        part = tactics._read_selection_part(data, 0, len(data), self.layout, 'test.fm')
        self.assertEqual(part.tactic_count, 1)
        self.assertEqual(data[part.end:], signature)
        self.assertEqual(part.slots[0], 123)

        bad_footer = self.selection(bytes.fromhex('01 05 02') + footer[3:], signature)
        displaced_tactic = self.selection(footer, b'\0' + signature)
        for data in (bad_footer, displaced_tactic):
            with self.subTest(data=data[-20:]), self.assertRaises(tactics.ReaderCheckError):
                tactics._read_selection_part(data, 0, len(data), self.layout, 'test.fm')

    def test_empty_and_counted_set_piece_headers(self):
        marker = self.layout.routine_area_marker
        prefix = marker + bytes(578 - len(marker))
        record = bytes(24) + b'\x01\x01'
        trailer = b'\0\0\0\0\x3c\0\1\0\0\0'
        zero = prefix + b'\0\0' + trailer
        extended = prefix + b'\x02\0' + record * 2 + trailer
        self.assertEqual(routine_header_bytes(zero, 0, len(zero), self.layout), 590)
        self.assertEqual(routine_header_bytes(extended, 0, len(extended), self.layout), 642)
        bad = bytearray(extended)
        bad[604] = 2
        self.assertEqual(routine_header_bytes(bad, 0, len(bad), self.layout), 590)

    def test_steam_27_1_tactic_signature_and_set_piece_header(self):
        current = tactics.find_tactics_layout(26, '27.1.0+2505117')
        updated = tactics.find_tactics_layout(26, '27.1.1+2511875')
        self.assertEqual(current.user_signature, bytes.fromhex('22 44 00 1b 01 00 00 00'))
        self.assertEqual(updated.user_signature, bytes.fromhex('22 44 00 1b 01 00 01 00'))
        self.assertEqual(updated.alternate_signature[-1], 2)
        self.assertEqual(self.layout.user_signature, bytes.fromhex('22 44 00 1b 00 01 00 00'))
        marker = current.routine_area_marker
        prefix = marker + bytes(578 - len(marker))
        record = bytes(24) + b'\x01\x01'
        footer = bytes.fromhex('00 00 00 00 3d 00 01')
        for count in (0, 2):
            data = prefix + struct.pack('<H', count) + record * count + footer
            self.assertEqual(routine_header_bytes(data, 0, len(data), current), 587 + 26 * count)
            self.assertEqual(routine_header_bytes(data, 0, len(data), updated), 587 + 26 * count)
