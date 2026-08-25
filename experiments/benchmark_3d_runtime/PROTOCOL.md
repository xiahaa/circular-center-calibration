# Table III protocol boundary

The paper fixes `n=64`, 1000 timing repetitions, the three method names, Xeon
hardware, and reported p50/p95/RSS values. It does not publish its worker or
memory-measurement code. This implementation divides exactly 1000 timed fits
across five sequential isolated processes per method and reports the median of
their process peak RSS values. Warmups are excluded from latency samples.
