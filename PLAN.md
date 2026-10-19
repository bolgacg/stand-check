# Plan, fixed before the measured runs were checked

Written 19 October 2026, before `study/run_study.py` was run on any measured run. Every change
after that point is listed at the bottom with its date and reason.

## The question

Before anyone analyses a test, someone has to decide whether the data acquisition recorded what
happened. This study asks whether a fixed set of checks, reading only the raw log and a channel
map written from the publisher's own documentation, finds three kinds of problem that a range
limit on every channel cannot see:

1. **Dropped samples**: rows that never arrived, rows the logger filled by repeating the last
   row, timestamps that repeat or run backwards, and streams whose length disagrees with the
   rest of the run.
2. **Stuck sensors**: a channel whose value stops changing while the stand is running, including
   a channel that never changes at all.
3. **Valve mismatches**: a valve whose electrical output, position feedback or downstream
   pressure does not follow its command within a stated time.

## Data

Three public stands, nothing else:

| Stand | Publisher | Licence | Runs |
|---|---|---|---|
| Liquid-engine hotfire controller logs | Nicholas Sterenberg, github.com/nsternie/engine_controller (commit 1bc832a) | BSD-3-Clause | 2 hotfires |
| Liquid-nitrogen fluid-hammer cold flow, FTTF, DLR Lampoldshausen | Klein, Traudt and Deeken, Zenodo 10.5281/zenodo.15526459 | CC BY 4.0 | 9 tests |
| GOx/methane resonance igniter bench, TU Delft | Neeser, 4TU.ResearchData 10.4121/dbaa8f0f-59d2-4d58-8cc9-494af1b966f1.v1 | CC BY 4.0 (data) | 96 files, of which 8 are empty |

## The split

Thresholds are set by looking at the **fit runs** only. The **measured runs** are checked once,
with the thresholds frozen, and every number on the page about detection and false alarms comes
from them. The split is by date, so it is not chosen by looking at the results:

- Sterenberg: fit = `test_data.csv` (first committed February 2019); measured = the 17 March 2018 hotfire.
- DLR: fit = the three tests of 3 August 2020; measured = the six tests of 5 and 6 August 2020.
- Delft: fit = the runs of 20 March 2024; measured = the runs of 3 April and 29 May 2024.

What I had seen of the measured runs before fixing this plan, stated so the reader can weigh it:
column-level summaries (minimum, maximum, longest repeat) of the 2018 hotfire, which showed four
thermocouples pinned at 1023 and 2047, six pressure channels pinned near -310 and -199, timing
gaps and two repeated timestamps; a timing summary of one Delft run from 29 May; and a research
note on the DLR set saying that one dynamic sensor (PD403) is frozen in two of nine tests, that
two dynamic sensors flat-top for 9 to 21 ms in the three hardest tests, and that the flowmeter
reports irregularly. The stuck threshold for fast pressure channels was not lowered to catch
the 9 to 21 ms flat tops; if they are missed, the miss is reported.

## The channel maps

Written from each publisher's documentation (README, overview PDF, mnemonics file, column
headers), not from the checker's output. Channels the documentation names are **live** and are
checked; channels it does not name are **spare** and are reported for information only.

- Sterenberg: pressures named in `mnemonics.csv` (2019 log) or headed `pressure[i] (psi)` (2018
  log), loads, thermocouples headed in degrees C, and the two valve positions. Housekeeping
  (battery, cycle times, counters) is not checked. Valves: every driver output whose command bit
  changes at least once in the run is checked against its output voltage; the two motorised
  valves are checked against their position feedback.
- DLR: all eight pressure channels, the temperature, the valve position, mass flow and density.
  No valve command is logged, so the valve check is reported as not possible.
- Delft: PS0, PS1, TC0 (ambient) and TC2 (resonator tip) are live in every run; PS2 (methane
  line) is live only in the six combustion runs of 29 May, the only runs that use methane. Main
  valve 1 is checked against PS0 and main valve 2 against PS2. The pressure rate is the README's
  2,500 a second; the files' own metadata says 5,000, which is reported as a note on every run.

## The checks and their thresholds

Each check gives every site (a stream, a channel or a valve) a score: how many times over its
threshold the worst evidence is. A site is flagged when its score is above 1. Sensitivity `s`
multiplies every threshold, so a site is flagged at sensitivity `s` when its score is above `s`;
`s = 1` is the setting fixed here.

| Check | Threshold at s = 1 | Why this value |
|---|---|---|
| Gap between timestamps | longer than the stream's median interval by more than max(0.5, 4 jitter) of it, where jitter is 1.4826 MAD / median | a single missing sample doubles an interval; jittery links need a wider allowance |
| Repeated or backwards timestamp | any | time cannot repeat or go back |
| Fewer rows than the declared rate | more than 2 percent short | the 2019 log is 0.4 percent short |
| Irregular stream (flowmeter) | interval over 0.25 s | the fit tests peak at 0.19 s |
| Whole row repeated (all live channels of a stream, at least three) | more rows in a row than chance would give once in 100 records, from how often each channel repeats its own previous value | first written as "one row"; changed before any measured run was checked, because the 150 kHz channels each repeat about 29 percent of the time, so three of them coincide thousands of times a record |
| Stream length disagrees with the reference stream (untimed files) | more than 10 percent | the fit runs' pressure and thermocouple files differ by up to 7 percent |
| Flat channel, fast pressure (1 kHz and up) | 50 ms | fit maximum is under 1 ms |
| Flat channel, slow pressure, load (under 1 kHz) | 0.5 s | fit maximum 0.22 s |
| Flat channel, temperature | 3 s | fit maximum 1.48 s |
| Flat channel, position, flow, density | 2 s | fit maximum 1.47 s (density after the valve shuts) |
| Range limit | outside the minimum to maximum of the stand's other runs, widened by 10 percent of that span, for 3 samples in a row | see the baseline below |
| Driver output against command | wrong state for 3 samples, more than 0.1 s after a command change; on means at least 75 percent of battery, off means at most 50 percent | fit outputs switch within 0.02 s |
| Motorised valve against setpoint | more than 10 degrees away, more than 1.5 s after a setpoint change | first written as 1.0 s; in the fit log the ox valve is still 9.5 degrees off at 0.95 s, so 1.0 s left no margin |
| Pressure response to a valve | half of a 2 bar step (1 bar for the methane line) reached within 1.0 s of the command, either side | fit responses arrive 0.0 to 0.9 s after the command; one fit run's second cycle arrives 1.8 s late, which is flagged |

A flat stretch has to be at least 5 samples long to count.

## The baseline

The check a team would otherwise rely on, apart from looking at plots, is a range limit on every
channel. Here it is set from the stand's other runs: the lowest and highest value the channel
showed in any other untouched run of the same stand where it moved at all, widened by a margin. A channel that appears
in only one run (the two hotfire logs name their channels differently) is limited by that run
itself, with hindsight. It is swept over its margin, from -50 percent to +200 percent of the span;
10 percent is its marked setting. The checker contains the same range limit, so the comparison
shows what the three new checks add. Doing nothing flags nothing.

The first version of this plan set the envelope at the 0.1 and 99.9 percentiles of all runs
including the one checked. On the fit runs that flagged the pressure surges of the DLR tests,
which are the event the tests exist to record, so it was changed before any measured run was
checked.

## Real data

Every flag raised at `s = 1` by the checker, and at 10 percent by the range limit, on every run
(fit and measured) is listed and labelled by hand as a real problem in the published data or a
false alarm, with the reason. A site is healthy unless it is labelled a real problem. Real
problems found by neither method are listed too, when I know of them.

## Planted faults

Planted into copies of measured runs, at healthy sites only, inside the active part of the run
(from one second before the first valve command to one second after the last). Seed 20261019.
Each kind and size is planted 30 times at a random run, site and time. The stands take turns,
so the 38 measured Delft runs do not drown out the single measured hotfire log.

| Kind | Sizes |
|---|---|
| Rows missing (timestamped streams) | 1, 2, 4, 8, 16, 32 rows |
| Rows repeated by the logger | 1, 2, 4, 8, 16, 32 rows |
| Channel frozen flat | 0.01, 0.03, 0.1, 0.3, 1, 3, 10 s |
| Channel frozen but still carrying its own noise | the same durations |
| Valve late against its command (output, position or pressure response) | 0.03, 0.1, 0.3, 1, 3 s, and never |

The frozen-with-noise kind is expected to be missed by every check here, because it is designed
to look like a working sensor whose port is blocked. It is in the study so the page can state
the blind spot with a number.

## Changes after the measured runs were checked

None yet.
