"""Presentation data for saved experiments and independently run comparisons."""
import hashlib
import json
import re


def numbered_name(base, jobs):
    base = (base or '手动战术').strip()[:84].rstrip() or '手动战术'
    numbers = [job['auto_name_number'] for job in jobs
               if job.get('auto_name_base') == base and type(job.get('auto_name_number')) is int]
    number = max(numbers, default=0) + 1
    occupied = {job.get('name') for job in jobs}
    while f'{base} #{number:02d}' in occupied:
        number += 1
    return {'name': f'{base} #{number:02d}', 'auto_name_base': base, 'auto_name_number': number}


def tactic_description(scenario, tested_side=0, include_opponent=False):
    team = scenario['teams'][tested_side]
    strategy = ('mentality', 'instructions', 'native_extra_team_bits', 'phases', 'setpieces')
    description = {'name': team.get('tactic_name'), 'team': team.get('name'),
                   'strategy': _digest({key: team.get(key) for key in strategy})}
    if include_opponent:
        opponent = scenario['teams'][1 - tested_side]
        description['opponent'] = {'name': opponent.get('tactic_name'), 'team': opponent.get('name')}
    return description


def old_tactics(job):
    """Recover labels for an older experiment from its own stored scenarios."""
    found = {}
    schedule = job.get('schedule', {})
    variants = ((label, row.get('group'), row.get('tested_side')) for label, row in schedule.items()
                if isinstance(row, dict)) if schedule else (
        (group, group, job.get('episode_settings', {}).get('tested_side', 0)) for group in ('A', 'B')
    )
    for label, group, side in variants:
        if group not in ('A','B') or side not in (0,1) or group in found or not re.fullmatch(r'[AB](?:_\d+_[HA])?', label):
            continue
        try:
            path = job['_dir'] / f'{label}.json'
            if path.stat().st_size > 2_000_000:
                continue
            scenario = json.loads(path.read_text(encoding='utf8'))
            found[group] = tactic_description(scenario, side, include_opponent=not schedule)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
    return found


def _digest(value):
    document = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(document.encode('utf8')).hexdigest()


def comparison_context(scenario, engine, seeds, *, save=None, opponents=None,
                       rounds=None, pool_draws=None, fixture=None):
    """Compare the B result while allowing changes to the tested team and its tactic."""
    own = scenario['teams'][0]
    compatibility = {
        'engine': engine.get('actual_dll_sha256'),
        'resources': engine.get('resource_fingerprint'),
        'fixture': fixture,
        'team': own.get('roster_source') or own['name'],
        'rules': scenario.get('rules'),
        'importance': scenario.get('match_importance'),
        'execution': scenario.get('experimental_execution'),
        'controlled_start': 'controlled-start-v3',
    }
    if save is None:
        pool = scenario.get('away_tactic_pool')
        compatibility['opponents'] = pool if pool and pool.get('enabled') else scenario['teams'][1]
    else:
        compatibility.update(save=save, opponents=sorted(opponents),
                             team=own.get('roster_source', {}).get('club_uid'), two_rounds=bool(rounds))
    report_seeds = sorted(rounds[-1]['seeds'] if rounds else seeds)
    sample = {'seeds': report_seeds}
    if pool_draws is not None:
        sample['draws'] = [pool_draws[seed] for seed in report_seeds]
    return {'settings': _digest(compatibility), 'sample': _digest(sample)}
