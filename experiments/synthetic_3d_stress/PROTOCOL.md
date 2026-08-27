# Figure 6 protocol boundary

The paper fixes the radius, nominal noise, point-count/arc grid, four angular
distributions, 1-cm success criterion, and 300 trials per cell. It does not
publish the random generator, within-band jitter, method thresholds, or trial
records. This directory therefore implements a deterministic statistical
reproduction. `protocol.yaml` records every recovered choice and keeps success
counts decoded from the PDF as approximate comparison data.
