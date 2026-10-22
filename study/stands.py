"""The three public stands: where each run comes from, and the channel map for each.

A run is a dict:
  stand, run_id, label, date, split ('fit' or 'measured'), source (file and checksum)
  streams:  {name: {'t': seconds, 'timing': 'regular'|'irregular'|'untimed', 'rate', 'declared_rate',
                    'max_interval', 'ref'}}
  channels: {name: {'stream', 'x', 'cls', 'unit', 'role', 'label'}}
  valves:   [{'name', 'kind', 'stream', 'cmd', 'fb', ... }]
  notes:    plain sentences for the report
  active:   (t0, t1), the part of the run between the first and last valve command, plus one second

The channel maps follow each publisher's documentation only: README, overview PDF, mnemonics
file and column headers. Channels the documentation names are 'live'; the rest are 'spare'.
"""
import glob, hashlib, json, os

import numpy as np

import _paths

RAW = _paths.RAW

STANDS = {
    'sterenberg': dict(
        title='Liquid-engine hotfire controller',
        publisher='Nicholas Sterenberg',
        where='github.com/nsternie/engine_controller',
        url='https://github.com/nsternie/engine_controller/tree/1bc832a4a362eef57493c53a33cf93ba2ee8b1e2/misc',
        licence='BSD-3-Clause',
        licence_url='https://github.com/nsternie/engine_controller/blob/1bc832a4a362eef57493c53a33cf93ba2ee8b1e2/license.txt',
        what='Two hotfire logs from the engine controller board, written at about 100 rows a second: '
             'tank, manifold and chamber pressures, four load cells and total thrust, thermocouples, '
             'two motorised main valves with their setpoints, and the command word and output voltage of '
             'every valve driver.'),
    'dlr': dict(
        title='Liquid-nitrogen fluid-hammer cold flow',
        publisher='Klein, Traudt and Deeken, DLR Lampoldshausen',
        where='Zenodo, doi 10.5281/zenodo.15526459',
        url='https://doi.org/10.5281/zenodo.15526459',
        licence='CC BY 4.0',
        licence_url='https://creativecommons.org/licenses/by/4.0/',
        what='Nine tests in which a fast valve stops a flow of liquid nitrogen in a 9.3 m feed line: '
             'five static pressures at 10,000 samples a second, three dynamic pressures at about '
             '150,000, the valve position, a temperature and a Coriolis flowmeter.'),
    'delft': dict(
        title='GOx/methane resonance igniter bench',
        publisher='Jonathan Neeser, TU Delft',
        where='4TU.ResearchData, doi 10.4121/dbaa8f0f-59d2-4d58-8cc9-494af1b966f1.v1',
        url='https://doi.org/10.4121/dbaa8f0f-59d2-4d58-8cc9-494af1b966f1.v1',
        licence='CC BY 4.0 (data)',
        licence_url='https://creativecommons.org/licenses/by/4.0/',
        what='Heating and combustion runs of a small igniter: three line and chamber pressures at '
             '2,500 samples a second, sixteen thermocouple inputs at 100, and the states of two main '
             'valves and a purge valve.'),
}

# Thresholds fixed in PLAN.md. Flat-channel limits are in seconds.
FLAT_LIMIT = {'p_fast': 0.05, 'p_slow': 0.5, 'load': 0.5, 'temp': 3.0, 'pos': 2.0, 'flow': 2.0, 'density': 2.0}
CLASS_WORDS = {'p_fast': 'pressure', 'p_slow': 'pressure', 'load': 'load', 'temp': 'temperature',
               'pos': 'valve position', 'flow': 'mass flow', 'density': 'density'}


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def active_from_edges(edges, t0, t1, pad=1.0):
    if not edges:
        return (t0, t1)
    return (max(t0, min(edges) - pad), min(t1, max(edges) + pad))


def edges_of(t, x):
    x = np.asarray(x)
    i = np.flatnonzero(np.diff(x) != 0) + 1
    return [float(t[j]) for j in i]


# ---------------------------------------------------------------- Sterenberg

def load_sterenberg():
    import pandas as pd
    runs = []
    d = os.path.join(RAW, 'sterenberg')
    for fn, split, label, date in [
            ('test_data.csv', 'fit', 'Hotfire log committed February 2019', '2019 (committed 2 Feb 2019)'),
            ('31718_hotfire_datalog_trimmed.csv', 'measured', 'Hotfire of 17 March 2018', '17 Mar 2018')]:
        path = os.path.join(d, fn)
        df = pd.read_csv(path)
        if fn == 'test_data.csv':
            tcol, vcol = 'time', 'vs'
            press = ['pom', 'pot', 'pft', 'pmom', 'pfm', 'pmnm', 'pc']
            spare = ['pc_hs']
            loads = ['l1', 'l2', 'l3', 'l4', 'lt']
            temps = ['thermocouple[0] (degC)', 'chamber_temp (degC)', 'thermocouple[2] (degC)', 'thermocouple[3] (degC)']
            servos = [('ox main valve', 'ox_valve_setpoint (deg)', 'rov'), ('fuel main valve', 'fuel_valve_setpoint (deg)', 'rfv')]
            names = {r['mnemonic']: r['name'] for _, r in pd.read_csv(os.path.join(d, 'mnemonics.csv')).iterrows()}
        else:
            tcol, vcol = 'Time (s)', 'valve_states ()'
            press = ['pressure[%d] (psi)' % i for i in range(16)]
            spare = []
            loads = ['load[%d] (lbs)' % i for i in range(4)] + ['thrust_load (lbs)']
            temps = ['thermocouple[%d] (degC)' % i for i in range(4)]
            servos = [('motorised valve 0', 'motor_setpoint[0] (degrees)', 'motor_position[0] ()'),
                      ('motorised valve 1', 'motor_setpoint[1] (degrees)', 'motor_position[1] ()')]
            names = {}
        t = df[tcol].to_numpy(float)
        streams = {'telemetry': dict(t=t, timing='regular', rate=None, declared_rate=float(df['samplerate (Hz)'].median()))}
        ch = {}

        def readable(col):
            # The 2018 log names its inputs only by number; say what kind of input each is.
            import re
            m = re.match(r'(pressure|load|thermocouple)\[(\d+)\]', col)
            if m:
                return {'pressure': 'Pressure input', 'load': 'Load cell', 'thermocouple': 'Thermocouple input'}[m.group(1)] + ' ' + m.group(2)
            if col.startswith('thrust_load'):
                return 'Thrust (sum of load cells)'
            return col

        def add(col, cls, unit, role, label=None):
            ch[col] = dict(stream='telemetry', x=df[col].to_numpy(float), cls=cls, unit=unit, role=role,
                           label=label or names.get(col, readable(col)))
        for c in press:
            add(c, 'p_slow', 'psi', 'live')
        for c in spare:
            add(c, 'p_slow', '', 'spare')
        for c in loads:
            add(c, 'load', 'lbs', 'live')
        for c in temps:
            add(c, 'temp', 'deg C', 'live')
        valves, cmd_edges = [], []
        word = df[vcol].to_numpy(int)
        ebatt = df['ebatt (Volts)'].to_numpy(float)
        for k in range(16):
            col = 'evlv[%d] (Volts)' % k
            bit = (word >> k) & 1
            if col not in df or not np.any(np.diff(bit)):
                continue        # outputs that are never commanded are not exercised in this run
            add(col, 'volt', 'V', 'valve', 'driver output %d voltage' % k)
            valves.append(dict(name='driver output %d' % k, kind='electrical', stream='telemetry',
                               cmd=bit.astype(float), fb=col, batt=ebatt, label='Valve driver output %d' % k))
            cmd_edges += edges_of(t, bit)
        for name, sp, pos in servos:
            add(pos, 'pos', 'deg', 'live', name[0].upper() + name[1:] + ' position')
            sp_x = df[sp].to_numpy(float)
            valves.append(dict(name=name, kind='position', stream='telemetry', cmd=sp_x, fb=pos,
                               label=name[0].upper() + name[1:]))
            cmd_edges += edges_of(t, sp_x)
        runs.append(dict(stand='sterenberg', run_id='sterenberg-' + ('2019' if split == 'fit' else '2018-03-17'),
                         label=label, date=date, split=split, source=dict(file='misc/' + fn, sha256=sha(path)),
                         streams=streams, channels=ch, valves=valves, notes=[],
                         active=active_from_edges(cmd_edges, t[0], t[-1])))
    return runs


# ---------------------------------------------------------------- DLR

DLR_TESTS = ['20200803_8', '20200803_11', '20200803_15', '20200805_9', '20200805_10',
             '20200806_5', '20200806_13', '20200806_15', '20200806_16']
DLR_STREAMS = [  # (file, stream, time column, channels with class and unit)
    ('Pressure', 'static pressure', 'Time_p', [('PS408', 'p_fast', 'bar', 'Static pressure PS408, station S1 by the valve'),
                                                ('PS405', 'p_fast', 'bar', 'Static pressure PS405, station S2 mid-line'),
                                                ('PS402', 'p_fast', 'bar', 'Static pressure PS402, station S3 by the supply tank'),
                                                ('PSHP', 'p_fast', 'bar', 'Supply (high-pressure) tank pressure'),
                                                ('PSLP', 'p_fast', 'bar', 'Receiving (low-pressure) tank pressure')]),
    ('Pressure_dyn', 'dynamic pressure', 'Time_dyn', [('PD409', 'p_fast', 'bar', 'Dynamic pressure PD409, station S1 beside PS408'),
                                                      ('PD406', 'p_fast', 'bar', 'Dynamic pressure PD406, station S2 beside PS405'),
                                                      ('PD403', 'p_fast', 'bar', 'Dynamic pressure PD403, station S3 beside PS402')]),
    ('Valve', 'valve', 'Time_valve', [('valve_pos', 'pos', 'mm', 'Fast valve position')]),
    ('Temperature', 'temperature', 'Time_temp', [('TI407', 'temp', 'K', 'Line temperature TI407, station S1')]),
    ('Coriolis', 'flowmeter', 'Time_cor', [('mflow_cor', 'flow', 'kg/s', 'Coriolis mass flow'),
                                           ('rho_cor', 'density', 'kg/m3', 'Coriolis density')]),
]


def load_dlr():
    runs = []
    base = os.path.join(RAW, 'dlr', 'PS-LN2-Set1')
    for test in DLR_TESTS:
        streams, ch, src = {}, {}, {}
        for kind, sname, tcol, chans in DLR_STREAMS:
            path = os.path.join(base, 'PS-LN2-' + test, 'PS-LN2-%s-%s.npz' % (test, kind))
            z = np.load(path)
            keys = {k.upper(): k for k in z.keys()}
            t = z[keys[tcol.upper()]] / 1000.0
            st = dict(t=t, timing='regular', rate=None, declared_rate=None)
            if sname == 'flowmeter':
                st.update(timing='irregular', max_interval=0.25)
            streams[sname] = st
            for c, cls, unit, label in chans:
                ch[c] = dict(stream=sname, x=z[keys[c.upper()]].astype(float), cls=cls, unit=unit, role='live', label=label)
        day = test[:8]
        runs.append(dict(stand='dlr', run_id='dlr-' + test, label='Test %s, %s %s Aug 2020' % (test, '', int(day[6:])),
                         date='%d Aug 2020' % int(day[6:]), split='fit' if day == '20200803' else 'measured',
                         source=dict(file='PS-LN2-Set1.7z / PS-LN2-%s' % test, md5_archive='b9488e2dd228a74e5a989e717ecfe650'),
                         streams=streams, channels=ch, valves=[],
                         notes=['No valve command is logged, only the valve position, so the valve check cannot be run.'],
                         active=(-1.0, float(streams['static pressure']['t'][-1]))))
        runs[-1]['label'] = 'Test %s (%d Aug 2020)' % (test.split('_')[1], int(day[6:]))
    return runs


# ---------------------------------------------------------------- Delft

DELFT_COMBUSTION = {'240529_084127', '240529_090559', '240529_091317', '240529_091626', '240529_092341', '240529_092957'}


def load_delft(include_empty=False):
    runs = []
    for path in sorted(glob.glob(os.path.join(RAW, 'delft', 'run_*.npz'))):
        rid = os.path.basename(path)[4:-4]
        z = np.load(path)
        meta = json.loads(str(z['meta']))
        date = {'240320': '20 Mar 2024', '240403': '3 Apr 2024', '240529': '29 May 2024'}[rid[:6]]
        split = 'fit' if rid.startswith('240320') else 'measured'
        if 'hs/PS data/PS0' not in z.files:
            if include_empty:
                runs.append(dict(stand='delft', run_id='delft-' + rid, empty=True, date=date, split=split))
            continue
        n_ps = len(z['hs/PS data/PS0'])
        n_st = len(z['hs/State/Main Valve 1 State'])
        n_th = len(z['th/TC data/TC0'])
        streams = {
            'pressure': dict(t=np.arange(n_ps) / 2500.0, timing='untimed', rate=2500.0, ref='thermocouple'),
            'valve state': dict(t=np.arange(n_st) / 100.0, timing='untimed', rate=100.0, ref='thermocouple'),
            'thermocouple': dict(t=np.arange(n_th) / 100.0, timing='untimed', rate=100.0, ref=None),
        }
        ch = {}
        comb = rid in DELFT_COMBUSTION
        for c, label in [('PS0', 'Oxygen line pressure'), ('PS1', 'Chamber pressure'), ('PS2', 'Methane line pressure')]:
            role = 'live' if (c != 'PS2' or comb) else 'spare'
            ch[c] = dict(stream='pressure', x=6250.0 * z['hs/PS data/' + c] - 24.0, cls='p_fast', unit='bar',
                         role=role, label=label)
        for i in range(16):
            c = 'TC%d' % i
            role = 'live' if i in (0, 2) else 'spare'
            label = {0: 'Ambient thermocouple', 2: 'Resonator tip thermocouple'}.get(i, 'Thermocouple input %d' % i)
            ch[c] = dict(stream='thermocouple', x=z['th/TC data/' + c].astype(float), cls='temp', unit='deg C', role=role, label=label)
        t_st = streams['valve state']['t']
        valves, edges = [], []
        for vname, col, resp, sign, step in [('main valve 1', 'Main Valve 1 State', 'PS0', 1, 2.0),
                                             ('main valve 2', 'Main Valve 2 State', 'PS2', -1, 1.0)]:
            cmd = z['hs/State/' + col].astype(float)
            if not np.any(np.diff(cmd)) or ch[resp]['role'] != 'live':
                continue
            valves.append(dict(name=vname, kind='response', stream='valve state', cmd=cmd, fb=resp, sign=sign, step=step,
                               label=vname[0].upper() + vname[1:] + ' against ' + ch[resp]['label'].lower()))
            edges += edges_of(t_st, cmd)
        purge = z['hs/State/Purge Valve State']
        edges += edges_of(t_st, purge)
        notes = ['The pressure channels carry no timestamps. Their metadata gives one sample every %.4f s (%d a second); '
                 'the dataset README gives 2,500 a second, which is what this check uses.'
                 % (meta.get('wf_increment/PS0', 0), round(1 / meta['wf_increment/PS0'])) if meta.get('wf_increment/PS0') else
                 'The pressure channels carry no timestamps; the README rate of 2,500 a second is used.',
                 'The valve states carry no timestamps and the README does not give their rate; 100 a second is assumed, '
                 'the rate of the thermocouple file.',
                 'The purge valve has no documented sensor that responds to it, so it is not checked.']
        runs.append(dict(stand='delft', run_id='delft-' + rid,
                         label='%s, %s' % (meta.get('title', rid), date), title=meta.get('title', ''),
                         description=meta.get('description', ''), date=date, split=split,
                         source=dict(file='data.zip / HighspeedData_%s.tdms + ThermalData_%s.tdms' % (rid, rid)),
                         streams=streams, channels=ch, valves=valves, notes=notes,
                         active=active_from_edges(edges, 0.0, float(t_st[-1]))))
    return runs


def load_all():
    return load_sterenberg() + load_dlr() + load_delft()
