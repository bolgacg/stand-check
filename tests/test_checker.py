"""Each rule on small made-up signals: it fires when it should and stays quiet when it should."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'study'))
import checker  # noqa: E402
import inject  # noqa: E402

RNG = np.random.default_rng(1)


def noisy(n, scale=1.0):
    return np.round(RNG.normal(0, scale, n) * 100) / 100


# ---------------------------------------------------------------- stuck

def test_flat_stretch_longer_than_limit_is_flagged():
    t = np.arange(2000) / 1000.0                      # 1 kHz, 2 s
    x = noisy(2000)
    x[500:700] = x[499]                                # 200 ms flat, fast-pressure limit 50 ms
    score, ev = checker.stuck(t, x, 'p_fast')
    assert score > 1 and abs(ev['seconds'] - 0.2) < 0.002 and not ev['whole']


def test_flat_stretch_shorter_than_limit_is_not_flagged():
    t = np.arange(2000) / 1000.0
    x = noisy(2000)
    x[500:530] = x[499]                                # 30 ms flat
    assert checker.stuck(t, x, 'p_fast')[0] < 1


def test_channel_that_never_changes_is_called_dead():
    t = np.arange(500) / 100.0
    score, ev = checker.stuck(t, np.full(500, -310.0), 'p_slow')
    assert score > 1 and ev['whole']


def test_short_repeats_below_five_samples_do_not_count():
    t = np.arange(100) / 1.0                           # 1 Hz: four equal samples span 3 s
    x = noisy(100)
    x[10:14] = x[10]
    assert checker.stuck(t, x, 'p_slow')[0] == 0


# ---------------------------------------------------------------- range

def test_three_samples_outside_are_needed():
    t = np.arange(100.0)
    x = np.zeros(100)
    x[50:52] = 50.0                                    # two samples far outside
    assert checker.range_mstar(t, x, -1.0, 1.0)[0] < 0
    x[52] = 50.0                                       # now three
    assert checker.range_mstar(t, x, -1.0, 1.0)[0] > 20


# ---------------------------------------------------------------- integrity

def stream(t, timing='regular', **kw):
    return dict(t=t, timing=timing, **kw)


def test_regular_stream_without_gaps_passes():
    t = np.arange(1000) / 100.0
    assert checker.integrity(stream(t), [], None)[0] < 1


def test_one_missing_row_on_a_clean_clock_is_flagged():
    t = np.delete(np.arange(1000) / 100.0, 400)
    assert checker.integrity(stream(t), [], None)[0] > 1


def test_repeated_timestamp_is_always_flagged():
    t = np.arange(1000) / 100.0
    t[300] = t[299]
    assert checker.integrity(stream(t), [], None)[0] == checker.ALWAYS


def test_short_record_against_declared_rate():
    t = np.sort(RNG.choice(np.arange(10000) / 100.0, 9000, replace=False))   # 10 percent of rows missing at random
    sc, ev = checker.integrity(stream(t, declared_rate=100.0), [], None)
    assert ev['parts']['short'] > 4


def test_untimed_stream_length_against_reference():
    st = stream(None, timing='untimed', rate=100.0)
    st['t'] = np.arange(2000) / 100.0                  # 20 s
    assert checker.integrity(st, [], 21.0)[0] < 1      # 5 percent apart
    assert checker.integrity(st, [], 25.0)[0] > 1      # 20 percent apart


def test_whole_rows_repeated_in_noisy_channels_are_flagged():
    t = np.arange(3000) / 1000.0
    xs = [noisy(3000) for _ in range(4)]
    assert checker.integrity(stream(t), xs, None)[0] < 1
    for x in xs:
        x[1000:1004] = x[999]
    assert checker.integrity(stream(t), xs, None)[0] > 1


def test_irregular_stream_uses_its_own_limit():
    t = np.cumsum(RNG.uniform(0.04, 0.08, 200))
    st = stream(t, timing='irregular', max_interval=0.25)
    assert checker.integrity(st, [], None)[0] < 1
    t2 = t.copy()
    t2[100:] += 0.3
    st['t'] = t2
    assert checker.integrity(st, [], None)[0] > 1


# ---------------------------------------------------------------- valves

def test_driver_output_that_follows_its_command_passes():
    t = np.arange(1000) / 100.0
    cmd = ((t > 2) & (t < 6)).astype(float)
    v = np.where(np.r_[0, cmd[:-1]] > 0, 12.0, 0.2)   # one sample late
    sc, _ = checker.valve_electrical(t, cmd, v, np.full(1000, 12.0))
    assert sc < 1


def test_driver_output_that_never_switches_is_flagged():
    t = np.arange(1000) / 100.0
    cmd = ((t > 2) & (t < 6)).astype(float)
    sc, _ = checker.valve_electrical(t, cmd, np.full(1000, 0.2), np.full(1000, 12.0))
    assert sc > 1


def test_motorised_valve_that_sticks_is_flagged():
    t = np.arange(1000) / 100.0
    sp = np.where(t > 2, 90.0, 0.0)
    pos = np.clip((t - 2) * 200, 0, 90) + RNG.normal(0, 0.5, 1000)
    assert checker.valve_position(t, sp, pos)[0] < 1
    pos[t > 2.2] = 40.0
    assert checker.valve_position(t, sp, pos)[0] > 1


def test_pressure_response_timing():
    tc = np.arange(3000) / 100.0
    cmd = ((tc > 10) & (tc < 20)).astype(float)
    tr = np.arange(75000) / 2500.0
    r = 1 + 12 * ((tr > 10.3) & (tr < 20.4)) + RNG.normal(0, 0.05, 75000)
    sc, ev = checker.valve_response(tc, cmd, tr, r, 1, 2.0)
    assert 0.25 < sc < 1 and len(ev['lags']) == 2
    sc, _ = checker.valve_response(tc, cmd, tr, 1 + RNG.normal(0, 0.05, 75000), 1, 2.0)
    assert sc == checker.NEVER_CAME


# ---------------------------------------------------------------- planting

def small_run():
    t = np.arange(1000) / 100.0
    chans = {c: dict(stream='s', x=noisy(1000) + 5 * k, cls='p_slow', unit='', role='live', label=c)
             for k, c in enumerate('abc')}
    return dict(stand='x', run_id='x-1', streams={'s': dict(t=t, timing='regular')}, channels=chans,
                valves=[], active=(1.0, 9.0))


def test_planted_missing_rows_are_removed_everywhere():
    run = small_run()
    new, key, info = inject.plant(run, 'stream:s', 'rows_missing', 8, np.random.default_rng(0))
    assert len(new['streams']['s']['t']) == 992 and all(len(c['x']) == 992 for c in new['channels'].values())
    assert len(run['streams']['s']['t']) == 1000       # the original is untouched


def test_planted_flat_segment_is_exactly_flat_and_noisy_one_is_not():
    run = small_run()
    new, _, info = inject.plant(run, 'channel:a', 'flat', 1.0, np.random.default_rng(0))
    sc, ev = checker.stuck(new['streams']['s']['t'], new['channels']['a']['x'], 'p_slow')
    assert sc > 1
    new, _, info = inject.plant(run, 'channel:a', 'flat_noisy', 1.0, np.random.default_rng(0))
    assert checker.stuck(new['streams']['s']['t'], new['channels']['a']['x'], 'p_slow')[0] < 1
