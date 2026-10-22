# stand-check

A post-test data check for rocket-engine and propulsion test stands. It reads a raw test log and a
channel map, and prints a pass or fail table for every record, channel and valve in the run:

| Check | What fails it |
|---|---|
| Dropped samples | A gap between timestamps longer than the record's own jitter allows, a timestamp that repeats or runs backwards, fewer rows than the declared rate gives, whole rows repeated by the logger more often than chance allows, or a record whose length disagrees with the rest of the run |
| Stuck sensor | A live channel that holds exactly the same value for longer than its type allows (50 ms for fast pressure, 0.5 s for slow pressure and load, 3 s for temperature, 2 s for position and flow) |
| Valve mismatch | A valve-driver output in the wrong state 0.1 s after its command, a motorised valve more than 10 degrees from its setpoint 1.5 s after a change, or a line pressure that does not answer a valve command within 1 s |
| Range limit | A channel outside the range it showed in the stand's other runs, widened by 10 percent |

Two comparisons sit beside it: the **plain checks** a stand would otherwise run (a flatline of more than
100 identical samples, and a timestamp interval of more than one and a half times the median), and the
range limit on its own, kept as a floor because the planted faults stay in range by design. A **rail
check** (a channel flat at its own highest or lowest value) was added after an outside review, once the
misses it fixes were known, and is reported apart from the planned result.

The page at **https://bolgacg.github.io/stand-check/** runs all of this on 99 public test-stand runs
from three projects, 49 of them measured with the thresholds frozen. On 960 faults planted into copies of
measured runs, the checker catches 485, the plain checks 257 and the range limit none, each with 5 false
alarms on 408 healthy sites. On the real logs it flags 46 of the 53 problems I labelled by hand, against
45 for the plain checks; most real problems are channels that never move. It loses to a plain flatline on
frozen fast channels, it cannot see a sensor that freezes but keeps its noise, and its freeze limits were
fitted on short student runs.

All data is public. It comes from Nicholas Sterenberg's engine-controller repository (BSD-3-Clause),
from DLR Lampoldshausen's liquid-nitrogen fluid-hammer set on Zenodo (CC BY 4.0), and from TU Delft's
resonance-igniter set on 4TU.ResearchData (CC BY 4.0). See `DATA-LICENCES.md`. None of it comes from
Rocket Lab, and nothing here describes Rocket Lab's systems. Built with Claude, an AI coding assistant.

## Run it

```
python3 study/fetch.py          # downloads the three sets (the 2 GB Delft archive is read entry by entry)
python3 study/run_study.py      # every number on the page, written to docs/data.js
pytest tests                    # unit tests of every rule
node study/parity.js            # the page's JavaScript checker against the Python build
node study/verify_page.js       # headless render, screenshots, overflow and walkthrough checks (needs playwright)
```

`fetch.py` checks each file against the checksum its publisher states. `run_study.py --list` prints
every site the checks flag on the real data; `data/adjudication.json` holds my label for each one (a
real problem or a false alarm, with the reason) and the real problems the planned checker missed. The
study refuses to run while any flagged site is unlabelled.

## How it was measured

`PLAN.md` fixes the checks, the thresholds, the split and the planting protocol. It was committed
before the measured runs were checked, and it lists the six changes made afterwards, with reasons.
Thresholds were set on the fit runs (the 2019 hotfire log, the DLR tests of 3 August 2020, and the
Delft runs of 20 March 2024). Every reported count comes from the other 49 runs.

## Layout

- `study/stands.py`: the three stands, how each run is loaded, and the channel maps, written from each
  publisher's documentation.
- `study/checker.py`: the checks. Each one gives a site a score, how many times over its threshold
  the worst evidence is, so the page can show every setting from the same numbers.
- `study/inject.py`: planting faults into copies of real runs.
- `study/run_study.py`, `study/build_page_data.py`: the study and the page data.
- `docs/`: the page. `checker.js` is a line-for-line port of the checks the page runs in the browser.
  `data.js` is generated; do not edit it.
- `tests/`: one test per rule on small made-up signals.

Code: MIT licence.
