# PR Reviewer: Performance Tuning Guide

## Profiling
```bash
python -m cProfile -o profile.out skills/pr-reviewer/main.py
```

## Key Bottlenecks
| Issue | Fix |
|-------|-----|
| Large diffs | Use `--unified=3`, cache in `.cache/` |
| LLM API calls | Batch similar checks, timeout 120s |
| Pattern matching | Pre-compile with `re.compile()` |
| OOM on 500+ files | Enable `low_memory_mode` |

## Memory
| PR Size | RAM | Flag |
|---------|-----|------|
| <100 | 50MB | default |
| 100-500 | 200MB | `--low-memory` |
| 500+ | 500MB+ | batch split |

## Config
```yaml
performance:
  cache_dir: .cache/pr-reviewer
  max_diff_lines: 50000
  llm_timeout: 120
  parallel_reviews: 4
```

## Troubleshooting
| Symptom | Solution |
|---------|----------|
| OOM | `low_memory_mode` |
| Timeout | increase `llm_timeout` |
| Stale cache | clear `.cache/` |
| High CPU | pre-compile patterns |
