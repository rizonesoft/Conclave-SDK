You are reviewing one short Python function. This is a test of the review pipeline. Do not modify any file and do not run anything.

```python
def window_sums(values, size):
    """The sum of every run of `size` consecutive values, in order.

    window_sums([1, 2, 3, 4], 2) == [3, 5, 7]
    """
    return [sum(values[i:i + size]) for i in range(len(values) - size)]
```

Report each defect as a numbered finding: what is wrong, an input that shows it, and the corrected line. Report findings only: no praise and no summary.

End with exactly one line: `OVERALL: needs-attention` if you found a defect, or `OVERALL: approve` if you found none.
